# WP4.4 Triage Dossier — `backend/services/bulk_detection_service.py`

Generated: 2026-09-17 (WP4.3 finding feed → WP4.4). **UNVERIFIED — no tests were executed**
(harness constraint: a live mutmut run owns this machine). Diffs taken with
`uv run mutmut show <key>` (all 147 succeeded, ~0.7 s each).

## Corpus

- `mutants/backend/services/bulk_detection_service.py.meta`: 294 keys total —
  **147 survived (exit_code 0)**, 147 killed, 0 unchecked.
- Covering test file (single, for every surviving function, per
  `mutants/mutmut-stats.json → tests_by_mangled_function_name`):
  **`backend/tests/unit/services/test_bulk_detection_service.py`** (504 lines).
- Source under test: `backend/services/bulk_detection_service.py` (469 lines).

### Anchor lines in the covering test file

| Test | lines | Why it matters |
|---|---|---|
| `test_bulk_insert_single_detection` | 184-206 | asserts success/count/ids + `commit` only |
| `test_bulk_insert_multiple_detections` | 208-226 | `duration_ms >= 0` (line 226) — no scale check |
| `test_bulk_insert_empty_list` | 228-238 | never asserts `duration_ms` (empty path) |
| `test_bulk_insert_with_all_fields` | 240-271 | captures `mock_session.execute.call_args` (line 270) then asserts only `is not None` (271) — **the one place statement content could have been asserted, and wasn't** |
| `test_bulk_insert_handles_database_error` | 273-289 | asserts `success is False`, `error_message`, `rollback` — nothing about returned fields or stats |
| `test_bulk_insert_chunked` | 313-337 | asserts `success` + `execute.call_count >= 2` only |
| `test_bulk_insert_with_conflict_handling` | 355-376 | passes `on_conflict="skip"` then asserts only `success is True` — ON CONFLICT SQL never inspected |
| `test_validate_detection_input` | 378-395 | two cases only: fully-valid + `confidence=1.5`. No boundaries, no bbox, no media_type, no missing-field cases |
| `test_bulk_insert_filters_invalid` | 397-425 | asserts `len(failed_inputs) == 1` but never *which* input |
| `test_get_insert_performance_stats` | 427-448 | `>= 6`, `>= 2`, `>= 0`, `>= 0` — every arithmetic mutant slips through |
| `test_reset_stats` | 493-504 | asserts only `total_inserts`/`total_batches`; `total_duration_ms` and `failed_inserts` never checked |

`grep -n "on_conflict\|_detection_to_dict\|index_elements"` over the whole test file returns
exactly **one** hit (line 373). No test in the repo compiles a statement from this service,
and no test calls `_detection_to_dict` directly.

---

## Cluster table (counts sum to 147)

| # | Cluster | N | Class | Example keys (suffix after `…BulkDetectionServiceǁ`) |
|---|---|---|---|---|
| A | `_detection_to_dict`: INSERT column-key names clobbered (`XXcamera_idXX` / `CAMERA_ID`) for all 18 payload columns | 36 | **TEST-GAP** | `_detection_to_dict__mutmut_1`, `_2`, `_33` |
| B | `bulk_insert`: ON CONFLICT clause — `== "skip"` → `!=` / `"XXskipXX"` / `"SKIP"`, and `index_elements=["camera_id","file_path"]` clobbers/`None` | 8 | **TEST-GAP** | `bulk_insert__mutmut_26`, `_28`, `_30` |
| C | `bulk_insert`: statement handed to `execute` / `RETURNING` target destroyed (`execute(None)`, `returning(None)`) | 2 | **TEST-GAP** | `bulk_insert__mutmut_36`, `_37` |
| D | `_stats` zero-initialisation invariant (`__init__` `0→1`, `0.0→1.0`; same in `reset_stats`) | 6 | **TEST-GAP** | `__init____mutmut_5`, `_11`, `reset_stats__mutmut_13` |
| E | `validate_detection`: boundary operator flips (required-field `or→and`; `< 0.0→<=`; `> 1.0→>=`; bbox `< 0 →<= 0 / < 1`; media `is not None → is None`) | 6 | **TEST-GAP** | `validate_detection__mutmut_1`, `_8`, `_17` |
| F | `validate_detection`: `valid_media_types` tuple clobbered (`"video"`→`"XXvideoXX"`/`"VIDEO"`) | 2 | **TEST-GAP** | `validate_detection__mutmut_22`, `_23` |
| G | `bulk_insert` empty/early-return path: `duration_ms=0.0`→`None`/`1.0`, kwargs dropped | 4 | **TEST-GAP** | `bulk_insert__mutmut_5`, `_12`, `_9` |
| H | `bulk_insert`: `failed_inputs.append(d)` → `append(None)` (identity of rejected input lost) | 1 | **TEST-GAP** | `bulk_insert__mutmut_18` |
| I | duration measurement arithmetic `… * 1000` → `/ 1000`, `+ start_time`, `* 1001` (success path, failure path, chunked) | 9 | **TEST-GAP** | `bulk_insert__mutmut_42`, `_85`, `bulk_insert_chunked__mutmut_28` |
| J | `bulk_insert` success-path stat accumulation (`total_batches += 1 → += 2`, `total_duration_ms += → =`) | 2 | **TEST-GAP** | `bulk_insert__mutmut_53`, `_54` |
| K | `bulk_insert` failure-path `BulkInsertResult` field values (`inserted_count=0→None/1`, `inserted_ids=[]→None/dropped`, `duration_ms→None/dropped`, `failed_inputs=detections→None/dropped`) | 9 | **TEST-GAP** | `bulk_insert__mutmut_113`, `_119`, `_121` |
| L | `bulk_insert` failure-path stat accumulation (`failed_inserts += → = / -=`) | 2 | **TEST-GAP** | `bulk_insert__mutmut_88`, `_89` |
| M | `bulk_insert_chunked`: chunk-loop bounds (`range(0,len,chunk_size)` → `range(0,chunk_size)`, `range(1,…)``, `range(0,len,)`) + `validate` default `False→True` + `validate=` kwarg dropped | 5 | **TEST-GAP** | `bulk_insert_chunked__mutmut_1`, `_12`, `_21` |
| N | `bulk_insert_chunked`: `total_inserted` accumulation (`=0→1`, `+= → = / -=`) | 3 | **TEST-GAP** | `bulk_insert_chunked__mutmut_7`, `_24`, `_25` |
| O | `bulk_insert_chunked`: aggregated `BulkInsertResult` field values (`inserted_count/ids/duration_ms/failed_inputs` → `None`/dropped) | 8 | **TEST-GAP** | `bulk_insert_chunked__mutmut_32`, `_35`, `_40` |
| P | `bulk_insert_chunked`: `validate=validate` → `validate=None` (falsy → identical control flow) | 1 | **EQUIVALENT** | `bulk_insert_chunked__mutmut_19` |
| Q | `get_performance_stats`: output key names clobbered (`failed_inserts`, `total_duration_ms`) | 4 | **TEST-GAP** | `get_performance_stats__mutmut_14`, `_19` |
| R | `get_performance_stats`: `round(total_duration, 2)` precision/arity mutants (`round(x,3)`, `round(x)`, `round(x,None)`, `round(2)`) | 4 | **TEST-GAP** | `get_performance_stats__mutmut_21`, `_24` |
| S | `get_performance_stats`: `avg_batch_size` / `avg_insert_time_ms` — div→mul, guard `> 0 → > 1`, `and False` short-circuit, `else 0 → 1` | 8 | **TEST-GAP** | `get_performance_stats__mutmut_27`, `_29`, `_40` |
| T | `bulk_insert` success-path **log call** + `extra` payload (message→`None`, `extra=None`/dropped, extra key clobbers, `round` in log) | 13 | **LOW-VALUE** | `bulk_insert__mutmut_58`, `_62`, `_70` |
| U | `bulk_insert` failure-path **log call** + `extra` payload (same shape as T, incl. `str(None)`) | 14 | **LOW-VALUE** | `bulk_insert__mutmut_92`, `_100`, `_107` |

**Totals: 147** — TEST-GAP 119, LOW-VALUE 27, EQUIVALENT 1.

### Cluster notes

- **A (36)** is the single biggest lever. `_detection_to_dict` is *executed* by 12 tests, yet no
  test asserts a single column name or the compiled INSERT text; `mock_session` swallows
  whatever dict is built. `test_bulk_insert_with_all_fields` (line 240) even names the
  statement it means to check and then asserts only `call_args is not None`. Every clobbered
  key (`BBOX_WIDTH`, `XXlabelsXX`, …) would be an `UnconsumedColumn`/unknown-column error in
  the real `pg_insert(Detection).values(...)`.
- **B+C (10)**: same root cause — the statement is never compiled. `on_conflict != "skip"`
  means the dedupe contract (`camera_id`,`file_path` unique index, NEM-3753) silently vanishes;
  `index_elements=["CAMERA_ID","file_path"]` would target a nonexistent index.
  `bulk_insert_with_conflict_handling` runs the branch and asserts only `success is True`.
- **D (6)** + Q: `test_reset_stats` asserts 2 of 4 counters; `test_get_insert_performance_stats`
  uses `>=`, so a service that *starts* with `total_inserts=1, total_duration_ms=1.0,
  failed_inserts=1` never trips anything. `failed_inserts` is asserted nowhere in the repo.
- **E+F (8)**: `validate_detection` is the ingestion gate. Mutant 1 (`or`→`and`) means a
  detection with an empty `camera_id` **but** a `file_path` is accepted (and vice-versa) —
  rows with NULL camera would reach Postgres. Mutants 8/10 reject legitimate `confidence`
  0.0/1.0; 17/18 reject legitimate zero-width/zero-height boxes; 22/23 reject `media_type="video"`
  (used by `test_bulk_insert_with_video_metadata`, which never validates); 26 rejects
  `media_type=None`. Only two probe cases exist (line 379-395).
- **G/H/K/L (16)**: the `except` branch returns a result object whose five fields are all
  unasserted; `failed_inputs=detections` is the caller's only recovery handle, and both the
  clobber (`→None`) and the arg-drop (`→ default []`) survive because the error test checks
  only `success`/`error_message`/`rollback`.
- **I (9)**: `duration_ms >= 0` cannot distinguish ms from seconds or a `+start_time` garbage
  value. Fix is a deterministic `perf_counter` fake, not a wall-clock bound (would also be a
  midnight/flake hazard per `memory/vitest-midnight-flake-window.md`-style timing fragility).
- **M/N/O (16)**: chunking is the whole point of the method. With `range(0, chunk_size)` the
  tail 50 of 150 detections are **never inserted** and `success` is still `True`; with
  `range(1, …)` boundaries shift and rows get inserted twice (the ON CONFLICT path would eat
  them silently). `test_bulk_insert_chunked` asserts `call_count >= 2` — satisfied by any
  wrong-but-multiple splitting. `validate` default `False→True` flips the documented contract
  (caller now gets silent filtering).
- **R (4)**: caveat — `round(x, None)` and `round(2)` should raise/mis-value at runtime, so
  their survival hints the mutmut verdict cache for these keys may be stale or the covering-test
  selection for them excluded the two stats tests. Drafted test D asserts exact rounding and
  will settle it; if these four survive that test, re-check the verdict direction for this key
  range before spending more time.
- **T/U (27)**: log text and `extra` keys only. Real change, but nothing should assert
  diagnostic payload; killing them means a `caplog` assertion per key, which is churn.
  **Leave surviving.** (If a future gate requires them, one `caplog` fixture test covers all 27.)
- **P (1)**: `validate=None` is falsy in `if validate:` — semantically identical. Killable
  only by a type assertion; declare `# no mutation` equivalent if the harness supports it.

---

## Drafted tests (6 highest-value clusters)

Target file: **`backend/tests/unit/services/test_bulk_detection_service.py`** (append to
`class TestBulkDetectionService`; fixtures `service` / `mock_session` / `sample_detections`
already exist at lines 24-74).

**TDD procedure (one line, same for all six): add the test, run it against the mutant copy —
the new assertion must fail — then run it against `backend/services/bulk_detection_service.py`
— it must pass. Only then is the cluster considered covered.**

// UNVERIFIED — not yet run red/green

### T1 — kills cluster A (36 mutants), and O's `failed_inputs` shape by proxy

```python
# module-level imports to add at the top of the test file (after `import pytest`)
from sqlalchemy.dialects import postgresql

from backend.models import Detection

    def test_detection_to_dict_uses_exact_detection_column_names(
        self, service: BulkDetectionService
    ) -> None:
        """_detection_to_dict keys must be real Detection column names (kills A).

        The dict feeds pg_insert(Detection).values(...) directly; a renamed key is an
        unknown-column error against Postgres, but every test here mocks the session,
        so nothing used to look at it.
        """
        detection = DetectionInput(
            camera_id="front_door",
            file_path="/export/foscam/front_door/image1.jpg",
            file_type="image/jpeg",
            object_type="person",
            confidence=0.95,
            bbox_x=100,
            bbox_y=200,
            bbox_width=50,
            bbox_height=100,
            detected_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
            media_type="image",
            duration=4.5,
            video_codec="h264",
            video_width=1920,
            video_height=1080,
            thumbnail_path="/path/to/thumb.jpg",
            enrichment_data={"license_plates": [{"plate": "ABC123"}]},
            labels=["person", "dog"],
        )

        payload = service._detection_to_dict(detection)

        expected_keys = {
            "camera_id", "file_path", "file_type", "object_type", "confidence",
            "bbox_x", "bbox_y", "bbox_width", "bbox_height", "detected_at",
            "media_type", "duration", "video_codec", "video_width", "video_height",
            "thumbnail_path", "enrichment_data", "labels",
        }
        # exact set equality: kills both XXkeyXX and UPPER clobbers
        assert set(payload) == expected_keys
        # every key must be a real column on the detections table
        assert set(payload) <= set(Detection.__table__.columns.keys())
        # values must survive unmoved
        assert payload["camera_id"] == "front_door"
        assert payload["file_path"] == "/export/foscam/front_door/image1.jpg"
        assert payload["bbox_width"] == 50
        assert payload["labels"] == ["person", "dog"]
        assert payload["enrichment_data"] == {"license_plates": [{"plate": "ABC123"}]}
        assert payload["detected_at"] == datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
```

`Detection` comes from `backend.models` (the same import the service itself uses). The
`postgresql` dialect import is reused by T2. If the repo's ruff gate flags runtime imports
that are only used in assertions, keep them at module level as written — both are needed at
call time, so they cannot move under `TYPE_CHECKING`.

### T2 — kills clusters B (8) + C (2)

```python
    @pytest.mark.asyncio
    async def test_on_conflict_skip_targets_the_dedupe_index(
        self, service: BulkDetectionService, mock_session: AsyncMock
    ) -> None:
        """on_conflict="skip" must emit ON CONFLICT (camera_id, file_path) DO NOTHING
        and a RETURNING clause (kills B + C)."""
        detection = DetectionInput(camera_id="front_door", file_path="/path/existing.jpg")
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(1,)]
        mock_session.execute.return_value = mock_result

        result = await service.bulk_insert([detection], on_conflict="skip")

        assert result.success is True
        stmt = mock_session.execute.call_args.args[0]  # mutant_36 passes None -> fails here
        sql = str(stmt.compile(dialect=postgresql.dialect()))
        assert "INSERT INTO detections" in sql
        assert "ON CONFLICT" in sql and "DO NOTHING" in sql
        # the conflict target must be exactly the two dedupe columns
        target = sql.split("ON CONFLICT", 1)[1].split("DO NOTHING", 1)[0]
        assert "camera_id" in target and "file_path" in target
        assert "XX" not in sql
        # RETURNING must still name the id column (kills mutant_37 returning(None))
        assert "RETURNING detections.id" in sql

    @pytest.mark.asyncio
    async def test_plain_insert_has_no_on_conflict_clause(
        self, service: BulkDetectionService, mock_session: AsyncMock
    ) -> None:
        """on_conflict=None must NOT emit ON CONFLICT (kills the != "skip" flip, mutant_26)."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(1,)]
        mock_session.execute.return_value = mock_result

        await service.bulk_insert([DetectionInput(camera_id="c", file_path="/p.jpg")])

        sql = str(mock_session.execute.call_args.args[0].compile(dialect=postgresql.dialect()))
        assert "ON CONFLICT" not in sql
        assert "RETURNING detections.id" in sql
```

The exact-target substring check plus `"XX" not in sql` are what kill the `index_elements`
clobbers; the `RETURNING detections.id` check is what kills `returning(None)` and
`execute(None)` (the latter makes `call_args.args[0].compile` raise, which is still a failure).

### T3 — kills clusters E (6) + F (2)

```python
    @pytest.mark.parametrize(
        ("kwargs", "expected"),
        [
            # required fields: EITHER one missing is invalid (kills mutant_1 or->and)
            ({"camera_id": "cam1", "file_path": "/p.jpg"}, True),
            ({"camera_id": "", "file_path": "/p.jpg"}, False),
            ({"camera_id": "cam1", "file_path": ""}, False),
            ({"camera_id": "", "file_path": ""}, False),
            # confidence boundaries are inclusive (kills mutants_8, _10)
            ({"camera_id": "c", "file_path": "/p.jpg", "confidence": 0.0}, True),
            ({"camera_id": "c", "file_path": "/p.jpg", "confidence": 1.0}, True),
            ({"camera_id": "c", "file_path": "/p.jpg", "confidence": -0.001}, False),
            ({"camera_id": "c", "file_path": "/p.jpg", "confidence": 1.001}, False),
            ({"camera_id": "c", "file_path": "/p.jpg", "confidence": None}, True),
            # bbox: zero is legal, negative is not (kills mutants_17, _18)
            ({"camera_id": "c", "file_path": "/p.jpg", "bbox_x": 0}, True),
            ({"camera_id": "c", "file_path": "/p.jpg", "bbox_height": 0}, True),
            ({"camera_id": "c", "file_path": "/p.jpg", "bbox_y": -1}, False),
            ({"camera_id": "c", "file_path": "/p.jpg", "bbox_width": -5}, False),
            ({"camera_id": "c", "file_path": "/p.jpg", "bbox_x": None}, True),
            # media type: image/video/None legal, anything else not (kills 22, 23, 26)
            ({"camera_id": "c", "file_path": "/p.jpg", "media_type": "video"}, True),
            ({"camera_id": "c", "file_path": "/p.jpg", "media_type": "image"}, True),
            ({"camera_id": "c", "file_path": "/p.jpg", "media_type": None}, True),
            ({"camera_id": "c", "file_path": "/p.jpg", "media_type": "audio"}, False),
            ({"camera_id": "c", "file_path": "/p.jpg", "media_type": "VIDEO"}, False),
        ],
    )
    def test_validate_detection_boundaries(
        self,
        service: BulkDetectionService,
        kwargs: dict[str, object],
        expected: bool,
    ) -> None:
        """Full truth table for the ingestion gate (kills E + F)."""
        assert service.validate_detection(DetectionInput(**kwargs)) is expected  # type: ignore[arg-type]
```

### T4 — kills cluster I (9)

```python
    @pytest.mark.asyncio
    async def test_duration_ms_is_measured_in_milliseconds(
        self,
        service: BulkDetectionService,
        mock_session: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """duration_ms must be (end-start)*1000 on the success path (kills I)."""
        stamps = [100.0, 101.5]  # 1.5 s elapsed -> 1500.0 ms
        monkeypatch.setattr(
            "backend.services.bulk_detection_service.time.perf_counter",
            lambda: stamps.pop(0) if stamps else stamps[-1],
        )
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(1,), (2,)]
        mock_session.execute.return_value = mock_result

        result = await service.bulk_insert(
            [DetectionInput(camera_id="c", file_path="/p.jpg")]
        )

        assert result.duration_ms == pytest.approx(1500.0)

    @pytest.mark.asyncio
    async def test_duration_ms_on_failure_is_also_milliseconds(
        self,
        service: BulkDetectionService,
        mock_session: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Same conversion on the rollback path (kills the _85/_86/_87 trio)."""
        stamps = [50.0, 50.25]
        monkeypatch.setattr(
            "backend.services.bulk_detection_service.time.perf_counter",
            lambda: stamps.pop(0) if stamps else stamps[-1],
        )
        mock_session.execute.side_effect = Exception("boom")

        result = await service.bulk_insert([DetectionInput(camera_id="c", file_path="/p.jpg")])

        assert result.success is False
        assert result.duration_ms == pytest.approx(250.0)

    @pytest.mark.asyncio
    async def test_chunked_duration_is_milliseconds(
        self,
        service: BulkDetectionService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Chunked wrapper measures its own elapsed time in ms (kills _27/_28/_29/_30)."""

        clock = {"t": 0.0}

        def fake_counter() -> float:
            value = clock["t"]
            clock["t"] += 2.0  # every read looks 2 s later than the previous one
            return value

        async def fake_chunk(*_a: object, **_k: object) -> BulkInsertResult:
            return BulkInsertResult(success=True, inserted_count=1, inserted_ids=[1])

        # stub bulk_insert so the chunk wrapper is the only perf_counter consumer left
        monkeypatch.setattr(service, "bulk_insert", fake_chunk)
        monkeypatch.setattr(
            "backend.services.bulk_detection_service.time.perf_counter", fake_counter
        )

        result = await service.bulk_insert_chunked(
            [DetectionInput(camera_id="c", file_path="/p.jpg")], chunk_size=1
        )

        assert result.duration_ms == pytest.approx(2000.0)
```

`bulk_insert` is stubbed because it consumes two `perf_counter()` reads of its own per chunk;
stubbing keeps the chunk wrapper's own start/end pair as the only consumer, so the ratio is
deterministic.

### T5 — kills clusters D (6) + Q (4) + R (4) + S (8) + J (2) + L (2)

```python
    def test_fresh_service_stats_are_all_zero(self, service: BulkDetectionService) -> None:
        """A brand-new service reports zeros for ALL FOUR counters (kills D's __init__ half,
        Q's key clobbers, S's `else 1` flips, R's round mutants on a 0.0 duration)."""
        stats = service.get_performance_stats()

        assert stats == {
            "total_inserts": 0,
            "total_batches": 0,
            "failed_inserts": 0,
            "total_duration_ms": 0.0,
            "avg_batch_size": 0,
            "avg_insert_time_ms": 0,
        }

    def test_reset_stats_zeroes_every_counter(
        self, service: BulkDetectionService
    ) -> None:
        """reset_stats is a full reset, not a two-field one (kills reset_stats_10/_13)."""
        service._stats.update(
            {"total_inserts": 100, "total_batches": 10,
             "total_duration_ms": 5.5, "failed_inserts": 7}
        )
        service.reset_stats()
        assert service.get_performance_stats() == {
            "total_inserts": 0, "total_batches": 0, "failed_inserts": 0,
            "total_duration_ms": 0.0, "avg_batch_size": 0, "avg_insert_time_ms": 0,
        }

    @pytest.mark.asyncio
    async def test_performance_stats_are_exact(
        self,
        service: BulkDetectionService,
        mock_session: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Exact arithmetic, not >= (kills J, L, and the avg_* mutants S/R)."""
        stamps = iter([0.0, 1.0, 2.0, 4.0])   # batch1 = 1000ms, batch2 = 2000ms
        monkeypatch.setattr(
            "backend.services.bulk_detection_service.time.perf_counter", lambda: next(stamps)
        )
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(1,), (2,)]
        mock_session.execute.return_value = mock_result
        detection = DetectionInput(camera_id="c", file_path="/p.jpg")

        await service.bulk_insert([detection])   # 2 inserts, batch 1
        await service.bulk_insert([detection])   # 2 inserts, batch 2
        mock_session.execute.side_effect = Exception("nope")
        await service.bulk_insert([detection])   # fails -> failed_inserts += 1

        assert service.get_performance_stats() == {
            "total_inserts": 4,
            "total_batches": 2,
            "failed_inserts": 1,
            "total_duration_ms": 3000.0,
            "avg_batch_size": 2.0,
            "avg_insert_time_ms": 1500.0,
        }
```

`avg_batch_size` uses `total_inserts / total_batches`; with 4/2 both operands are ints so the
value is exactly `2.0`. This single dict-equality assertion kills all 8 `avg_*` mutants
(`/`→`*`, `>0`→`>1`, `and False`, `else 0`→`1`), the 4 `round()` variants, both stat
accumulators in `bulk_insert`, and both in the `except` branch.

### T6 — kills clusters G (4) + H (1) + K (9) + M (5) + N (3) + O (8)

```python
    @pytest.mark.asyncio
    async def test_empty_input_result_is_fully_zeroed(
        self, service: BulkDetectionService, mock_session: AsyncMock
    ) -> None:
        """The early-return path must report a real zero duration (kills G)."""
        result = await service.bulk_insert([])
        assert result.duration_ms == 0.0
        assert result.inserted_ids == []
        assert result.failed_inputs == []
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_failed_inputs_are_the_rejected_inputs_themselves(
        self, service: BulkDetectionService, mock_session: AsyncMock
    ) -> None:
        """filtered-out inputs are returned by identity, not as placeholders (kills H)."""
        bad = DetectionInput(camera_id="cam1", file_path="/path/invalid.jpg", confidence=1.5)
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(1,)]
        mock_session.execute.return_value = mock_result

        result = await service.bulk_insert(
            [DetectionInput(camera_id="cam1", file_path="/path/valid.jpg"), bad],
            validate=True,
        )

        assert result.failed_inputs == [bad]
        assert result.failed_inputs[0].file_path == "/path/invalid.jpg"

    @pytest.mark.asyncio
    async def test_failure_result_reports_input_for_recovery(
        self, service: BulkDetectionService, mock_session: AsyncMock
    ) -> None:
        """On DB error the caller still gets count 0 / no ids / the inputs it handed in
        (kills K)."""
        detections = [
            DetectionInput(camera_id="cam1", file_path="/path/1.jpg"),
            DetectionInput(camera_id="cam1", file_path="/path/2.jpg"),
        ]
        mock_session.execute.side_effect = Exception("connection reset")

        result = await service.bulk_insert(detections)

        assert result.success is False
        assert result.inserted_count == 0
        assert result.inserted_ids == []
        assert result.failed_inputs == detections          # kills _113 / _119
        assert result.duration_ms >= 0                     # kills _81 / _111 / _117 (None)
        assert isinstance(result.duration_ms, float)

    @pytest.mark.asyncio
    async def test_chunking_splits_exact_chunks_and_aggregates(
        self, service: BulkDetectionService, mock_session: AsyncMock
    ) -> None:
        """150 detections at chunk_size=100 -> exactly 2 statements, sizes [100, 50],
        150 ids, 150 inserted, no failures (kills M, N, O)."""
        detections = [
            DetectionInput(camera_id="cam1", file_path=f"/path/image_{i}.jpg")
            for i in range(150)
        ]
        chunk_sizes: list[int] = []

        async def fake_chunk(chunk: list[DetectionInput], **kwargs: object) -> BulkInsertResult:
            chunk_sizes.append(len(chunk))
            ids = list(range(1, len(chunk) + 1))
            return BulkInsertResult(
                success=True, inserted_count=len(chunk), inserted_ids=ids,
                duration_ms=1.0, failed_inputs=list(kwargs.get("failed", [])),
            )

        monkeypatch_stub = fake_chunk  # readability
        import unittest.mock as _m

        with _m.patch.object(service, "bulk_insert", side_effect=fake_chunk):
            result = await service.bulk_insert_chunked(detections, chunk_size=100)

        assert chunk_sizes == [100, 50]                    # kills _12/_13/_14 loop mutants
        assert result.success is True
        assert result.inserted_count == 150                # kills _7/_24/_25
        assert len(result.inserted_ids) == 150             # kills _33/_38
        assert result.failed_inputs == []                  # kills _35/_40
        assert result.duration_ms >= 0                     # kills _27/_34/_39

    @pytest.mark.asyncio
    async def test_chunked_propagates_validate_and_defaults_to_false(
        self, service: BulkDetectionService
    ) -> None:
        """chunked must pass validate through verbatim and default it to False
        (kills M's _1 and _21)."""
        import unittest.mock as _m

        detections = [DetectionInput(camera_id="cam1", file_path="/p.jpg")]
        with _m.patch.object(service, "bulk_insert", new_callable=_m.AsyncMock) as spy:
            spy.return_value = BulkInsertResult(success=True, inserted_count=1)
            await service.bulk_insert_chunked(detections, chunk_size=10)
            assert spy.await_args.kwargs["validate"] is False   # default contract

        with _m.patch.object(service, "bulk_insert", new_callable=_m.AsyncMock) as spy:
            spy.return_value = BulkInsertResult(success=True, inserted_count=1)
            await service.bulk_insert_chunked(detections, chunk_size=10, validate=True)
            assert spy.await_args.kwargs["validate"] is True    # kwarg actually forwarded
```

`is` (not `==`) on the `validate` assertion is what kills `validate=None` in principle;
cluster P is still classified EQUIVALENT because `None` is falsy inside `bulk_insert`, so the
behavioural difference is unreachable — this assertion is a contract pin, not a behaviour test.

---

## Suggested handling for the non-gap survivors

- **T/U (27 LOW-VALUE)**: exclude from the score target, or one `caplog`-based test asserting
  `record.extra` key sets on the two log calls if the gate demands a number. Do not write 27
  separate assertions.
- **P (1 EQUIVALENT)**: `validate=None` — mark equivalent in the baseline.
- **R (4)**: run T5 first; if these four still report survived, the surviving verdict itself is
  suspect (`round(x, None)` raises `TypeError`) — re-check those keys against a fresh mutmut
  pass before treating them as real gaps.
