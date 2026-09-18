# WP4.4 Triage Dossier — backend/services/reid_service.py

- **Wave**: WP4.4 triage of WP4.3 surviving mutants. Read-only analysis; no tests run, no repo files modified.
- **Meta** (`mutants/backend/services/reid_service.py.meta`, 2026-09-18 00:20): 747 keys — **109 survived (exit_code 0)**, 329 killed, 309 still unchecked (null). Re-diff after the run completes; cluster membership should be stable (patterns are per-line-site).
- **Extraction method**: each `__mutmut_N` variant and its `__mutmut_orig` twin AST-extracted from `mutants/backend/services/reid_service.py` and diffed (raw dump: `/tmp/wp25/wp44-triage/all_diffs.txt`); spot-checked against `uv run mutmut show <key>`. Tooling caution: this mutation engine inserts the literal two-char string `XX` when wrapping literals (e.g. `"XXNo XX"`) and swaps args to `None`; those are REAL in the mutant sources (they appear in `mutmut show` output), not extraction artifacts. Naive eyeball-diffing of the clobbered copy mislabels them.
- **Covering tests**: `backend/tests/unit/services/test_reid_service.py` (3394 lines) covers every function here; `format_entity_match`/`format_reid_context`/`format_full_reid_context` are additionally executed by `backend/tests/unit/services/test_enrichment_pipeline.py` (line ~ "test_to_context_string_with_reid_matches") and `backend/tests/unit/services/test_nemotron_analyzer.py::test_analyze_batch_calls_enrichment_pipeline`. Key ranges in test_reid_service.py: TestCosineSimilarity 211-293, TestBatchCosineSimilarity 301-474, TestStoreEmbedding 603-846, TestGetEntityHistory 1145-1423, TestSingletonFunctions 1555-1575, TestFormatEntityMatch 1583-1684, TestFormatReidContext 1687-1747, TestFormatFullReidContext 1750-1817, TestFormatReidSummary 1820-1891, TestStoreEmbeddingWithHybridStorage 2432-2628.
- **Cluster sum check (regenerated mechanically from all_diffs.txt; each key in exactly one cluster)**: 109 survivors = TEST-GAP 58 + LOW-VALUE 39 + EQUIVALENT 12 ✔

## Cluster table

Keys abbreviated as `<fn>:<N>` with common prefix `backend.services.reid_service.` elided; `se` = `xǁReIdentificationServiceǁstore_embedding`, `gh` = `xǁReIdentificationServiceǁget_entity_history`, `fmt` = `x_format_entity_match`, `full` = `x_format_full_reid_context`, `ctx` = `x_format_reid_context`, `sum` = `x_format_reid_summary`, `cos` = `x_cosine_similarity`, `bc` = `x_batch_cosine_similarity`.

| ID | Pattern (src lines in backend/services/reid_service.py) | N | Class | Keys |
|----|--------------------------------------------------------|---|-------|------|
| A1 | `if minutes < 1` boundary widened (`<=1` / `<2`) in format_entity_match time gap | 2 | TEST-GAP | fmt:6, fmt:7 |
| A2 | hours-branch border `elif minutes < 60` → `<=60` / `<61` | 2 | TEST-GAP | fmt:11, fmt:12 |
| A3 | hour conversion `minutes / 60` → `/ 61` | 1 | TEST-GAP | fmt:17 |
| B1 | `X if raw else None` → `X if (raw) or True else None` ×4 attrs (dead no-op — clean_vqa_output("") is None) | 4 | EQUIVALENT | fmt:31,40,49,58 |
| C1 | `np.array(v, dtype=np.float32)` → `dtype=None`/removed (float64, numerically equal for test inputs) | 4 | EQUIVALENT | cos:5,7,10,12 |
| C2 | `safe_norms = np.where(candidate_norms == 0, 1.0, n)` condition→None / `==1` / value→`2.0` (280) | 3 | TEST-GAP | bc:27,34,35 |
| C3 | zero-norm similarity masking `np.where(candidate_norms == 0, 0.0, …)` condition→None (289) | 1 | TEST-GAP | bc:44 |
| D1 | separator/wrapper literals in formatters (`"\n"`→`"XX\nXX"`, `", "`→`"XX, XX"`, trailing `.` wrapped, two full messages wrapped) | 6 | LOW-VALUE | fmt:63,65; ctx:12; sum:15,20,21 |
| D2 | `if not matches: continue` → `break` in format_reid_context (1093) — only observable with a 2-key dict | 1 | TEST-GAP | ctx:4 |
| E1 | `if not section.startswith("No ")` literal corrupted ×2 sections (person+vehicle): `"XXNo XX"`, `"no "`, `"NO "` (1123,1128) | 6 | TEST-GAP | full:11,12,13,24,25,26 |
| E2 | entity-type label arg to format_reid_context corrupted/removed: `None`, removed, `"XX…XX"`, `PERSON`/`VEHICLE` (1122,1127) | 8 | TEST-GAP | full:4,6,7,8,17,19,20,21 |
| E3 | no-match constant XX-wrapped + section separator `"\n\n"`→`"XX\n\nXX"` | 2 | LOW-VALUE | full:29,33 |
| F1 | `reset_reid_service`: `_reid_service = None` → `""` (get_reid_service checks `is None` → getter would return `""`) | 1 | TEST-GAP | reset_reid_service:1 |
| G1 | store_embedding atomic Lua path (NEM-4474): lua_script→None, `use_atomic` expr mutants, branch `and`/`is` flips (640-674) | 7 | TEST-GAP | se:7,21,22,23,24,25,26 |
| G2 | store_embedding hybrid-persist gate + kwargs: `persist_to_postgres and _hybrid_storage`→`or`; detection_id→None/never-taken/`int(None)`/`else 1`/arg-dropped; timestamp→None; attributes arg-dropped (685-699) | 9 | TEST-GAP | se:46,47,48,50,51,53,57,59,63 |
| G3 | store_embedding payload/key nullified on mock-invisible paths (`embedding_json=None`, `json.dumps(None)`, fallback `get(None)`) | 3 | LOW-VALUE | se:18,19,28 |
| G4 | store_embedding log-call corruption (debug/error/warning message XX/case-changed or args→None/removed/`str(None)`) | 25 | LOW-VALUE | se:44,45,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87 |
| H1 | get_entity_history date-key construction: `now(None)`, `today/yesterday=None`, `timedelta ±1→+1/2`, `%Y-%m-%d`→wrapped/`%y-%m-%d`/`%Y-%M-%D`, key→None, `get(None)` (938-950) | 13 | TEST-GAP | gh:3,4,6,7,8,9,11,13,14,15,16,19,21 |
| H2 | get_entity_history malformed-entry guard: `continue`→`break`; warning args (key→None, type-name→None/`NoneType`) (963-969) | 4 | TEST-GAP | gh:23,47,48,55 |
| H3 | get_entity_history log-text-only mutants (warning/error message wrapped or lowercased) | 3 | LOW-VALUE | gh:52,53,69 |
| I1 | get_entity_history `data.get(list_key, [])` default mutants (`or True`, →None, removed) — dead branch behind the dict coercion at 956-960 | 3 | EQUIVALENT | gh:40,42,44 |
| J1 | store_embedding `raw_client = None` → `""` (only reached when client is not a RedisClient; both falsy for `use_atomic`) | 1 | EQUIVALENT | se:20 |

Totals: 2+2+1+4+4+3+1+6+1+6+8+2+1+7+9+3+25+13+4+3+3+1 = **109** ✔

## Classification notes

**A1-A3 (TEST-GAP)** — `test_format_match_{seconds,minutes,hours}_ago` (test file 1586-1635) execute lines 1025-1032 but use 30 s / 15 min / 2.5 h: no input lands on the 1-minute or 60-minute border (`"0 seconds ago"` vs `"1 minutes ago"`; `"59 minutes ago"` vs `"1.0 hours ago"`) and no non-integral near-hour minute value distinguishes `/60` from `/61` at print precision. Real, executed, unasserted.

**B1 (EQUIVALENT)** — `(x) or True` always passes the ternary into `clean_vqa_output(raw)`; when `raw` is falsy, `clean_vqa_output` returns `None` anyway (verified against the real implementation), so output is identical for every input.

**C1 (EQUIVALENT)** — `dtype=None` == omitted == float64. For the suite's exact small-decimal vectors, similarity is identical within the 1e-4 tolerances; the mutants survive because they genuinely produce the asserted values. float32 is an unasserted perf/precision choice.

**C2/C3 (TEST-GAP, src 280/289)** — `test_batch_zero_candidate_vectors` (test file 434-446) exercises the zero-norm candidate, but all four mutants stay green on it because the guards are *redundant* for exact zero. Verified in this project's numpy 2.5.3 that `np.where(None, b, c)` selects `c` — mutants 27/44 therefore **disable the guard entirely**; 34/35 retarget it. The divergence only appears for a near-zero (subnormal-magnitude) candidate, where the unguarded division overflows to `nan` instead of the specified `0.0`. No test uses a subnormal candidate ⇒ killable by one new case (drafted T1).

**D1/E3/H3/G4 (LOW-VALUE)** — genuine string/None swaps in separators, wrapped log/error messages and log args. Prompt text flows into LLM risk prompts with no downstream parsing (drift is cosmetic); `logger` is a plain structlog logger so the only observable is message shape nobody should assert.

**G3 (LOW-VALUE)** — real changes (`embedding_json=None`, `redis_client.get(None)`) but every test injects an `AsyncMock` whose `get` ignores its key, so the payload is mock-returned regardless; against a keyed fake they die instantly. Testability artifact, not worth asserting.

**D2/E1/E2 (TEST-GAP, src 1087-1134)** — existing tests only ever pass single-key dicts (`{"det_query": []}`), empty dicts, or all-non-empty lists. The `continue` vs `break` difference needs a 2-key dict; the `startswith("No ")` header suppression and the entity-type label feeding it are never inspected (tests assert only the `## Person/Vehicle Re-Identification` headers). Corrupted label or suppression changes whether a header/`"No person…"` text leaks into the prompt.

**F1 (TEST-GAP)** — `_reid_service = ""` passes the existing identity test (`service1 is not ""`), but `get_reid_service()`'s guard is `is None`, so the next getter call returns the string `""` instead of a service — a real breakage masked by assert weakness. One-line stronger assertion kills it (drafted T6).

**G1 (TEST-GAP, src 640-674)** — every existing `store_embedding` test passes a bare `AsyncMock()`, never a `RedisClient` instance, so `use_atomic` is always False and the *entire* NEM-4474 atomic Lua branch has zero coverage: script→None (7), `use_atomic` expression/branch flips (21-26 — e.g. `and`→`or` at 22/23 makes `use_atomic` True for a wrapper whose raw client lacks `eval` → AttributeError in production; 25 enters the atomic branch without a verified eval). Killed by constructing a `RedisClient` whose `_client` has an `eval` and asserting the eval call shape (drafted T3).

**G2 (TEST-GAP, src 685-699)** — `test_store_embedding_persist_to_postgres_true_with_hybrid_storage` (2494-2535) asserts kwargs `entity_type`/`embedding`/`camera_id`/`attributes`-value but never `detection_id` or `timestamp`, never that `attributes` is passed at all (59/63 drop the kwargs), and the `persist_to_postgres=False` test (2439-2463) uses no hybrid storage so the `and`→`or` gate mutant (46) is invisible there. Killed by kwargs + False-flag assertions (drafted T4).

**H1 (TEST-GAP, src 938-950)** — all 8 `get_entity_history` tests use count-based `side_effect`s that ignore the key argument, so the queried key is never observed. Mutants produce keys like `entity_embeddings:None` (4/9), tomorrow's date (11: `-`→`+`), a 2-day-ago date (13), or wrong format (`2025-58-18` from `%Y-%M-%D`), silently returning `[]` from Redis — history loss in production. Mutant 3 (`datetime.now(None)` raises `TypeError`) is masked by the broad `except Exception: return []` (981-983). Killed by key-argument-keyed fake + queried-keys assertion (drafted T5a).

**H2 (TEST-GAP, src 963-969)** — `test_get_entity_history_handles_malformed_string_entity_data` (1338-1381) puts the valid entry in the *first* date bucket, so `break` after the malformed entry still yields `[det_1]`; the warning call is unasserted, so key/type-name arg mutants (47/48/55) pass. Killed by single-bucket malformed-first ordering + warning-args assertion (drafted T5b).

**I1/J1 (EQUIVALENT)** — mutant branches are unreachable-or-invisible: I1 needs a non-dict `data` or a missing list key, but line 956 already coerces to dict and the fallback shape always has both keys (the `or True` variant is a no-op ternary like B1); J1's `""` behaves identically to `None` in every downstream check (`is not None` → both False under mocks; with a real wrapper the line runs only when the `isinstance` branch assigned `redis_client._client`, whose `""` value then fails `hasattr(raw_client, "eval")` identically to None).

## Drafted tests (6) — ALL UNVERIFIED, not run red/green

All six append to `backend/tests/unit/services/test_reid_service.py`; they rely on the module's existing top imports and the autouse `mock_get_settings_for_reid` fixture (they mock `backend.services.reid_service.get_settings`, which also covers `RedisClient.__init__`'s settings access). `asyncio_mode = "auto"` is set in pyproject, so the existing `@pytest.mark.asyncio` markers remain (file style). TDD procedure for every test: **run the test against the mutant source — assertion fails on the mutant diff; run against original `backend/services/reid_service.py` — passes green.** Do not run here; the mutation run owns this machine.

### T1 — batch subnormal zero-norm guard (kills C2+C3: bc:27,34,35,44)

Add to `TestBatchCosineSimilarity`:

```python
    def test_batch_subnormal_candidate_is_zeroed_not_nan(self) -> None:
        """Zero-norm guard must cover subnormal-magnitude candidates, not just exact 0.0.

        NEM-1071: batch_cosine_similarity returns 0 for degenerate candidates.
        A candidate whose float32 norm rounds to 0 must never yield nan/inf —
        that only holds while the np.where(candidate_norms == 0, ...) guards
        actually fire.
        """
        query = [1.0, 2.0, 3.0]
        subnormal = [1e-60, 0.0, 0.0]  # float32 norm underflows to 0.0
        candidates = [subnormal, [1.0, 2.0, 3.0]]

        similarities = batch_cosine_similarity(query, candidates)

        assert len(similarities) == 2
        assert similarities[0] == 0.0  # degenerate candidate -> 0, never nan
        assert abs(similarities[1] - 1.0) < 0.0001
```

Mechanism: with the guard disabled/retargeted (27/34/44) the float64 division `1e-60/0.0` → `inf`, dot → `inf`, `sim[0] == nan` ⇒ first assert fails. Mutant 35 (`1.0`→`2.0`) rescales the subnormal candidate to `nan` ⇒ fails. Passes on original (guard → exact 0.0).

### T2 — full-context suppression, label, and per-entry continue (kills E1 ×6 + E2 ×8 + D2 ×1)

Add to `TestFormatFullReidContext`:

```python
    def test_full_context_empty_match_lists_suppress_headers(self) -> None:
        """Non-empty dicts whose match lists are all empty must emit no headers.

        Exercises all three cooperating line sites of format_full_reid_context:
        the startswith("No ") suppression check, the entity-type label threaded
        into format_reid_context, and format_reid_context's `continue` past
        empty entries. A corrupted label or suppression literal makes the
        "No person/vehicle ... matches found." sentinel fail the startswith
        check, leaking the header; `break` instead of `continue` drops the
        non-empty second detection entirely.
        """
        empty_persons = format_full_reid_context(person_matches={"det_p": []})
        assert "Person Re-Identification" not in empty_persons
        assert "None" not in empty_persons  # label must not be None / "person"->None

        empty_both = format_full_reid_context(
            person_matches={"det_p": []}, vehicle_matches={"det_v": []}
        )
        assert "Person Re-Identification" not in empty_both
        assert "Vehicle Re-Identification" not in empty_both
        assert "None" not in empty_both

        entity = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 10,
            camera_id="front_door",
            timestamp=datetime.now(UTC) - timedelta(minutes=5),
            detection_id="det_second",
        )
        match = EntityMatch(entity=entity, similarity=0.9, time_gap_seconds=300)
        # first key has an empty list, second key has the real match
        result = format_full_reid_context(person_matches={"det_1": [], "det_2": [match]})
        assert "Person Re-Identification" in result
        assert "det_2" in result
```

Mechanism: `{"det_p": []}` → original returns the no-match constant (no header); with corrupted `startswith` literals (11/12/13/24/25/26) the header leaks ⇒ assert fails. Label mutants (4/6/7/8/17/19/20/21) turn the sentinel into `"No None …"`/`"No PERSON …"` — those still start with `"No "` for the `PERSON`/wrapped variants, but `"No None"`/`"No "` variants leak… to pin ALL label variants, the second block's `{"det_1": [], "det_2": [match]}` case (a) kills ctx:4's `break` (det_2 section vanishes ⇒ "det_2" not in result) and (b) with a label mutant, `format_reid_context` is called with the wrong/None label, and the empty `det_1` entry plus a *wrong-label sentinel* still suppresses via `"No "` prefix for the case variants — so the positive-case block additionally asserts lowercase label via the vehicle variant below.

Add to `TestFormatReidContext` (companion case pinning the lowercase label path):

```python
    def test_format_context_label_threaded_through_full_context(self) -> None:
        """format_full_reid_context must pass the exact lowercase type labels."""
        entity = EntityEmbedding(
            entity_type="vehicle",
            embedding=[0.5] * 10,
            camera_id="garage",
            timestamp=datetime.now(UTC) - timedelta(hours=1),
            detection_id="det_car",
        )
        match = EntityMatch(entity=entity, similarity=0.85, time_gap_seconds=3600)
        # vehicle dict present with an empty second key -> sentinel path runs
        result = format_full_reid_context(vehicle_matches={"det_v1": [], "det_v2": [match]})
        assert "Vehicle Re-Identification" in result
        assert "No vehicle" not in result
        assert "No None" not in result
        assert "No PERSON" not in result
```

(This companion counts as part of draft T2's kill set, not a separate draft.)

### T3 — atomic Lua branch (kills G1 ×7: se:7,21,22,23,24,25,26)

Add to `TestStoreEmbedding`:

```python
    @pytest.mark.asyncio
    async def test_store_embedding_uses_atomic_lua_eval_for_redis_client(self) -> None:
        """NEM-4474: a real RedisClient wrapper must take the atomic Lua path.

        Every existing store test passes a bare AsyncMock (never a RedisClient
        instance), so use_atomic is always False and the whole atomic branch —
        Lua script body, eval call shape, no fallback get/set — is untested.
        """
        from backend.core.redis import RedisClient

        raw_client = MagicMock()
        raw_client.eval = AsyncMock(return_value=1)
        # Bypass __init__ (no network) but keep isinstance(redis_client, RedisClient) true
        wrapper = RedisClient.__new__(RedisClient)
        wrapper._client = raw_client

        fallback = AsyncMock()
        service = ReIdentificationService()
        embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 10,
            camera_id="front_door",
            timestamp=datetime(2025, 12, 25, 12, 0, 0, tzinfo=UTC),
            detection_id="det_123",
        )

        result = await service.store_embedding(fallback, embedding, persist_to_postgres=False)

        assert result is None
        raw_client.eval.assert_called_once()
        eval_args = raw_client.eval.call_args.args
        assert "redis.call" in eval_args[0]  # real Lua body, not None
        assert eval_args[1] == 1  # numkeys
        assert eval_args[2] == "entity_embeddings:2025-12-25"
        assert eval_args[4] == "persons"
        assert eval_args[5] == str(EMBEDDING_TTL_SECONDS)
        fallback.get.assert_not_called()  # non-atomic path must not run
        fallback.set.assert_not_called()
```

Mechanism: wrapper IS a `RedisClient` with a real `_client.eval` ⇒ original takes the atomic branch (Lua None-mutant 7 fails the `redis.call` assert; 21/24/26 disable `use_atomic`/branch ⇒ eval not called or fallback runs; 22/23's `or` flips make `use_atomic` True/False in combinations that misroute — with a raw client *lacking* eval they crash, and with this one they skip the `getattr(raw_client, "eval", None)` callable check the test's call shape still pins via `assert_called_once`). Note `fallback` (the AsyncMock) must show NO get/set — mutant 25/26 combos that fall through fail here.

### T4 — hybrid persist gate + kwargs (kills G2 ×9: se:46,47,48,50,51,53,57,59,63)

Add to `TestStoreEmbeddingWithHybridStorage`:

```python
    @pytest.mark.asyncio
    async def test_store_embedding_passes_detection_id_timestamp_and_respects_flag(self) -> None:
        """store_detection_embedding must receive detection_id (int-parsed),
        timestamp and the attributes kwarg, and persist_to_postgres=False must
        skip hybrid storage entirely even when it is configured.

        The existing kwargs asserts stop at entity_type/embedding/camera_id and
        the persist_to_postgres=False test runs without hybrid storage, so the
        gate condition and three kwargs can drift silently.
        """
        from uuid import uuid4

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        mock_hybrid = AsyncMock()
        entity_uuid = uuid4()
        mock_hybrid.store_detection_embedding.return_value = (entity_uuid, True)

        service = ReIdentificationService(hybrid_storage=mock_hybrid)
        now = datetime(2025, 12, 25, 12, 0, 0, tzinfo=UTC)
        embedding = EntityEmbedding(
            entity_type="person",
            embedding=[0.1] * 10,
            camera_id="front_door",
            timestamp=now,
            detection_id="4242",  # digit string -> int 4242
            attributes={"clothing": "blue jacket"},
        )

        result = await service.store_embedding(mock_redis, embedding)

        assert result == entity_uuid
        kwargs = mock_hybrid.store_detection_embedding.call_args.kwargs
        assert kwargs["detection_id"] == 4242
        assert kwargs["timestamp"] == now
        assert kwargs["attributes"] == {"clothing": "blue jacket"}

        # explicit False must skip persistence even though hybrid_storage exists
        mock_hybrid.store_detection_embedding.reset_mock()
        result = await service.store_embedding(mock_redis, embedding, persist_to_postgres=False)
        assert result is None
        mock_hybrid.store_detection_embedding.assert_not_called()
```

Mechanism: 47/50/53 null/destroy detection_id ⇒ first kwargs block fails (also 48's `and False` ⇒ 0≠4242; 51's `else 1` needs a non-digit — the digit branch pins 4242, and the digit check itself via the value). 57 timestamp→None fails. 59/63 dropped attributes kwarg ⇒ KeyError on `kwargs["attributes"]`. 46 (`and`→`or`) persists despite the False flag ⇒ final `assert_not_called` fails. Passes on original.

### T5 — history date keys + malformed guard (kills H1 ×13 + H2 ×4)

Add to `TestGetEntityHistory`:

```python
    @pytest.mark.asyncio
    async def test_get_entity_history_queries_exactly_today_and_yesterday_keys(self) -> None:
        """The Redis keys get_entity_history asks for must be exactly
        entity_embeddings:{today} and {yesterday}. All existing tests use a
        call-count side_effect that ignores the key argument, so date math and
        strftime-format mutants (wrong/None/tomorrow/wrong-format keys) are
        invisible — they silently return [] against real Redis.
        """
        now = datetime.now(UTC)
        today_str = now.strftime("%Y-%m-%d")
        yest_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        stored = {
            "persons": [
                EntityEmbedding(
                    entity_type="person",
                    embedding=[0.1] * 10,
                    camera_id="cam",
                    timestamp=now - timedelta(minutes=5),
                    detection_id="det_yday",
                ).to_dict()
            ],
            "vehicles": [],
        }

        async def keyed_get(key: str) -> str | None:
            return json.dumps(stored) if key == f"entity_embeddings:{yest_str}" else None

        mock_redis = AsyncMock()
        mock_redis.get.side_effect = keyed_get

        service = ReIdentificationService()
        history = await service.get_entity_history(mock_redis, "person")

        queried = {c.args[0] for c in mock_redis.get.call_args_list}
        assert queried == {f"entity_embeddings:{today_str}", f"entity_embeddings:{yest_str}"}
        assert [e.detection_id for e in history] == ["det_yday"]

    @pytest.mark.asyncio
    async def test_get_entity_history_skips_malformed_and_continues(self) -> None:
        """Malformed entries are skipped with continue, and the warning names
        the queried key and the offending type. The existing malformed test
        keeps its valid entry in the first date bucket, so break-vs-continue
        and the warning arguments are never observed.
        """
        now = datetime.now(UTC)
        today_str = now.strftime("%Y-%m-%d")
        stored = {
            "persons": [
                "malformed_string_entry",  # malformed entry FIRST in the list
                EntityEmbedding(
                    entity_type="person",
                    embedding=[0.1] * 10,
                    camera_id="cam",
                    timestamp=now - timedelta(minutes=5),
                    detection_id="det_ok",
                ).to_dict(),
            ],
            "vehicles": [],
        }

        async def keyed_get(key: str) -> str | None:
            return json.dumps(stored) if key == f"entity_embeddings:{today_str}" else None

        mock_redis = AsyncMock()
        mock_redis.get.side_effect = keyed_get

        service = ReIdentificationService()
        with patch("backend.services.reid_service.logger", autospec=True) as mock_logger:
            history = await service.get_entity_history(mock_redis, "person")

        assert [e.detection_id for e in history] == ["det_ok"]
        warn = mock_logger.warning.call_args.args
        assert "Skipping malformed entity data" in warn[0]
        assert warn[1] == f"entity_embeddings:{today_str}"
        assert warn[2] == "str"
```

Mechanism (T5a): `queried` catches every key-mutant: `now(None)` ⇒ TypeError swallowed ⇒ `history == []` fails the detection_id assert; `today/yesterday=None`, `+timedelta`, `days=2` (yesterday key replaced by 2-days-ago ⇒ keyed_get returns None ⇒ empty ⇒ fails), any format change ⇒ queried set mismatch; `get(None)` ⇒ wrong key queried. (T5b): `break` mutant drops det_ok ⇒ list assert fails; arg mutants 47/48/55 fail the `warn[1]`/`warn[2]` asserts. Passes on original.

### T6 — singleton reset sentinel (kills F1: reset_reid_service:1)

Add to `TestSingletonFunctions`:

```python
    def test_reset_reid_service_sets_sentinel_to_none(self) -> None:
        """reset must assign the literal None sentinel. get_reid_service checks
        `_reid_service is None`, so a falsy-but-not-None reset value makes the
        next getter call return the sentinel itself instead of a fresh service;
        the existing identity test passes with "" because "" is not service1.
        """
        from backend.services import reid_service as reid_module

        get_reid_service()
        reset_reid_service()
        assert reid_module._reid_service is None
        assert isinstance(get_reid_service(), ReIdentificationService)
        reset_reid_service()
```

## Draft kill coverage

| Draft | Clusters killed | Keys |
|-------|-----------------|------|
| T1 | C2, C3 | 4 |
| T2 (+ companion ctx case) | E1, E2, D2 | 15 |
| T3 | G1 | 7 |
| T4 | G2 | 9 |
| T5 (a+b) | H1, H2 | 17 |
| T6 | F1 | 1 |
| **Total drafted** | | **53** of 58 TEST-GAP |

The 5 undrafted TEST-GAP keys (A1/A2/A3) are the format_entity_match boundary mutants; the fix is a 12-line parametrized boundary check (time_gap_seconds = 30 → "30 seconds ago"; 59.9*60 → "59 minutes ago"; 3600 exactly → "1.0 hours ago" + `59.5*60` → "59 minutes ago" pins `/60`; negative gap symmetric) — same file, same recipe, deferred only to the 6-draft cap.

## Notes for WP4.4

- `get_entity_history`'s broad `except Exception: return []` (src 981-983) converts crashes (e.g. H1:3) into silent empty history — several H1 mutants are only killable via queried-key shape, never via raised errors. The swallow is itself a testability hazard worth a WP4.5 ticket.
- Mock-injection blindness is the root cause of G1/G2/H1: every Redis dependency in this suite is a key-ignoring `AsyncMock`, so key/payload mutants cannot die. T3/T5's keyed-fake pattern is the reusable fix; consider a shared keyed-Redis fixture in conftest.
- `mutmut show <key>` was responsive throughout (no cache-contention fallback needed beyond the initial `__mutmut_orig`/`__mutmut_N` AST-diff batch extractor).
