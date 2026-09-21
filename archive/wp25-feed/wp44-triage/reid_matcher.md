# WP4.4 Triage Dossier — backend/services/reid_matcher.py

- **Survivors:** 100 of 234 checked (125 killed, 9 pending) — source: `mutants/backend/services/reid_matcher.py.meta`
- **Covering test file (only one):** `backend/tests/unit/services/test_reid_matcher.py` (1090 lines)
- **Full raw diffs:** `/tmp/wp25/wp44-triage/_rm_all_diffs.txt` (all 100, via `uv run mutmut show <key>`)
- **Structural root cause:** every DB-touching test uses `AsyncMock()` for the session and a canned `MagicMock` result. `await self.session.execute(stmt)` returns the canned rows **regardless of `stmt`**, and no test ever inspects the statement. That single gap explains the 26 SQL-shape survivors in `find_matches` and the 5 in `store_embedding`. Sibling suite precedent for fixing this: `backend/tests/unit/services/test_search.py:532-592` (`result.compile(dialect=postgresql.dialect()); assert "..." in str(compiled)`).

## Key naming note

`mutmut show` diffs render every expression in the file as `__mutmut_orig(...)`, so "the whole call looks wrapped" is display noise. The real mutation is the inner clobber (e.g. `__mutmut_orig(__mutmut_original_none)` = arg replaced by `None`; `__mutmut_orig("XX?...XX")` = string clobber). Classifications below are derived from the actual clobbered expression, not the wrapper.

## Per-cluster table

PRE (find_matches region): the file's `find_matches` survivors map to source lines: cutoff=159, stmt build=163-174, exclude=176-177, execute=179, loop=189-204, threshold=196, ReIDMatch ctor=197-204, debug log=209-214, default arg=127.

| # | Cluster (function / concern) | Count | Class | Example keys (≤3) | Evidence / note |
|---|---|---|---|---|---|
| 1 | `find_matches` — WHERE/predicate structure clobbered: `select(None)`, whole `and_(...)`→`None`, each clause (cutoff / `isnot(None)` / JSONB `op("?")("reid_embedding")`) → `None` or removed, `>=`→`>`, op/key strings clobbered, `execute(None)` — src L163-179 | 15 | TEST-GAP | `…find_matches__mutmut_13`, `__mutmut_18`, `__mutmut_25` | Line executes on every test; tests never inspect the statement passed to `execute()`. Against a real DB each mutant returns wrong rows or errors. Kill = compile the executed statement and assert on it (draft T1). |
| 2 | `find_matches` — ORDER BY dropped: `order_by(None)`, `desc(None)` — L173 | 2 | TEST-GAP | `__mutmut_12`, `__mutmut_27` | Same inspection gap; recency order is the stated contract ("searched recent detections"; ties resolved by recency). Kill = T1. |
| 3 | `find_matches` — `exclude_detection_id` handling: guard flipped `is not None`→`is None`, `stmt = None`, `.where(None)` no-op, `!=`→`==` — L176-177 | 4 | TEST-GAP | `__mutmut_28`, `__mutmut_31` | `test_excludes_detection_id` (test_reid_matcher.py:385-411) only asserts `mock_session.execute.called` — it comments "we just check the call". Kill = T2. |
| 4 | `find_matches` — time cutoff computed wrong: `-`→`+` (future window), `datetime.now(UTC)`→`now(None)` (naive local) — L159 | 2 | TEST-GAP | `__mutmut_8`, `__mutmut_9` | `TestTimeWindowFiltering` (test_reid_matcher.py:495-532) only asserts `execute.called`; the bind param is never examined. Kill = T1 (cutoff param: tz-aware + in the past). |
| 5 | `find_matches` — empty-embedding `logger.warning` message text clobbers (`None`/XX/lower/upper) — L155 | 4 | EQUIVALENT | `__mutmut_3`, `__mutmut_4` | Message-text only; `logger.warning(None)` formats fine. No behavior. |
| 6 | `find_matches` — no-recent-detections `logger.debug` message text clobbers — L183 | 4 | EQUIVALENT | `__mutmut_36` | Same. |
| 7 | `find_matches` — summary `logger.debug` msg→`None`, args→`None`, args removed — L209-214 | 8 | LOW-VALUE | `__mutmut_66`, `__mutmut_70` | Arg clobbers make the log record fail to format, but `logging` swallows handler errors — no app-visible behavior; nobody should assert debug text. |
| 8 | `find_matches` — summary `logger.debug` message text clobbers — L210 | 3 | EQUIVALENT | `__mutmut_74` | Message-text only. |
| 9 | `find_matches` — default `max_results: int = 10`→`11` — L127 | 1 | TEST-GAP | `__mutmut_1` | Public default cap; `test_respects_max_results` (test_reid_matcher.py:327-351) always passes `max_results=3` explicitly. Killable by feeding 11 canned detections, no kwarg, asserting `len(matches)==10`. (Low priority.) |
| 10 | `find_matches` — `continue`→`break` when a detection has no extractable embedding — L192 | 1 | TEST-GAP | `__mutmut_44` | `test_skips_detection_without_embedding` (test_reid_matcher.py:465-487) puts the embedding-less detection **last**, so break==continue there. Order-swap kills it (draft T5a). |
| 11 | `find_matches` — threshold `similarity >= self.threshold`→`>` — L196 | 1 | TEST-GAP | `__mutmut_50` | `test_exact_threshold_match_included` (test_reid_matcher.py:876-900) cheats: identical embedding = sim 1.0 > 0.7, so `>` still passes. Exact-boundary case never tested. Kill = T5b. |
| 12 | `find_matches` — `ReIDMatch(timestamp=…)` → `timestamp=None` — L201 | 1 | TEST-GAP | `__mutmut_54` | No test asserts `match.timestamp` produced by `find_matches` (only the standalone dataclass test). Kill = T5c. |
| 13 | `_get_reid_embedding` — guards weakened: `isinstance(dict) and "vector" in …` → `or` (L237), `if vector is not None` → `or True` (L239) | 2 | TEST-GAP | `__mutmut_8`, `__mutmut_16` | Mutant 8 crashes (KeyError) on dict-without-vector payloads; mutant 16 crashes (`list(None)` → TypeError) on `{"vector": None}`. Tests only cover valid dict and bad-string forms. Kill = T6a. |
| 14 | `_cosine_similarity` — math wrong: magnitude exponents `**0.5`→`**1.5` (both), `dot / (m1*m2)` → `dot * (m1*m2)` and → `dot / (m1/m2)` — L260-266 | 4 | TEST-GAP | `__mutmut_20`, `__mutmut_33` | Every existing cosine test uses normalized/orthogonal vectors, where `sum²==1` hides exponent errors and dot=0 hides operator flips. Non-normalized inputs expose all four (draft T4a). |
| 15 | `_cosine_similarity` — `zip(..., strict=False)` → `strict=None` / removed / `strict=True` — L259 | 3 | EQUIVALENT | `__mutmut_15` | `None` is falsy = `False`; removed kwarg defaults to `False`; `strict=True` unreachable because the length-equality guard at L255 already guarantees equal lengths. |
| 16 | `_cosine_similarity` — empty guard `len(vec1) == 0`→`== 1` — L255 | 1 | TEST-GAP | `__mutmut_4` | 1-dim vectors now short-circuit to 0.0. Tests use dims 0/3/128/512 only. Kill = T4b. |
| 17 | `store_embedding` — lookup query/execute clobbered: `stmt=None`, `select(None)`, `.where(None)`, `Detection.id ==`→`!=`, `execute(None)` — L293-294 | 5 | TEST-GAP | `…store_embedding__mutmut_1`, `__mutmut_4` | Same execute-blindness; would load the wrong detection (or all) in production. Kill = T3. |
| 18 | `store_embedding` — not-found `logger.warning` message text clobbers — L298 | 3 | EQUIVALENT | `__mutmut_13` | Message-text only. |
| 19 | `store_embedding` — not-found `logger.warning` args dropped (`msg, )`) — L298 | 1 | LOW-VALUE | `__mutmut_12` | Format failure swallowed by logging internals. |
| 20 | `store_embedding` — `self._compute_embedding_hash(embedding)` → `(None)` — L302 | 1 | TEST-GAP | `__mutmut_18` | Stored `hash` becomes the hash of the string `"None"` for every detection — dedup/lookup metadata destroyed. Test only asserts `"hash" in payload`. Kill = T3. |
| 21 | `store_embedding` — payload key renames: `"model"`→`"XXmodelXX"`/`"MODEL"`, `"stored_at"`→`"XXstored_atXX"`/`"STORED_AT"` — L311-316 | 4 | TEST-GAP | `__mutmut_30`, `__mutmut_34` | Stored JSON contract (read back by `_get_reid_embedding` consumers / API surface). Tests assert only vector/dimension/hash-exists. Kill = T3. |
| 22 | `store_embedding` — payload `"model"` value clobbers (`"XXosnet_ain_x1_0XX"`, `"OSNET_AIN_X1_0"`) — L315 | 2 | TEST-GAP | `__mutmut_32` | Same contract; model provenance is the point of the field (NEM-5562). Kill = T3. |
| 23 | `store_embedding` — `stored_at` timestamp made naive: `datetime.now(UTC)`→`now(None)` — L316 | 1 | TEST-GAP | `__mutmut_36` | Stores naive local ISO time in an audit field. Kill = T3 (fromisoformat + tzinfo). |
| 24 | `store_embedding` — success `logger.debug` msg→`None`, args→`None`, args removed — L322-327 | 8 | LOW-VALUE | `__mutmut_37`, `__mutmut_42` | Logging internals only; swallowed. |
| 25 | `store_embedding` — success `logger.debug` message text clobbers — L323 | 3 | EQUIVALENT | `__mutmut_45` | Message-text only. |
| 26 | `store_embedding` — log arg `embedding_hash[:8]`→`[:9]` — L326 | 1 | EQUIVALENT | `__mutmut_48` | Truncation length of a debug log argument only. |
| 27 | `_compute_embedding_hash` — codec alias `"utf-8"`→`"UTF-8"` — L342 | 1 | EQUIVALENT | `__mutmut_8` | Python codec names are case-insensitive; identical bytes/hash. |
| 28 | `is_known_person` — `max_results=1` → `None` / removed / `2` (fetch-limit optimization only; returns `matches[0]` either way) — L371-375 | 3 | LOW-VALUE | `…is_known_person__mutmut_4` | Observable return identical; internal fetch ceiling not worth asserting directly. (Incidentally covered by T7's spy if you choose to assert wrapper kwargs.) |
| 29 | `is_known_person` — `time_window_hours=time_window_hours` passthrough dropped (falls back to 24) — L373 | 1 | TEST-GAP | `__mutmut_6` | `test_uses_custom_time_window` (test_reid_matcher.py:685-701) only asserts `execute.called`. Kill = T7a (cutoff param ≈ now−48h). |
| 30 | `get_person_history` — forwarded kwargs clobbered: `max_results=100`→`None`/removed(→default 10)/`101`, window passthrough dropped — L407-411 | 4 | TEST-GAP | `…get_person_history__mutmut_5`, `__mutmut_6` | Removing `max_results` silently truncates history to 10 — real contract break; window drop widens/narrows history. Tests never inspect forwarded args. Kill = T7b (spy). |
| 31 | `get_sightings_by_camera` — forwarded kwargs clobbered (same four as #30) — L437-441 | 4 | TEST-GAP | `…get_sightings_by_camera__mutmut_6`, `__mutmut_7` | Same; drop of `max_results` truncates grouped counts to 10. Kill = T7c (spy). |
| 32 | `get_sightings_by_camera` — grouped list `append(match)` → `append(None)` — L449 | 1 | TEST-GAP | `__mutmut_16` | `TestGetSightingsByCamera` asserts only keys and `len(...)` — never the elements. Every element becomes `None`. Kill = T6b. |
| 33 | `get_reid_matcher` — factory passes `session=None` into the matcher — L481-484 | 1 | TEST-GAP | `x_get_reid_matcher__mutmut_1` | `test_factory_function` (test_reid_matcher.py:234-238) checks isinstance+threshold, not session wiring. One-line kill = T6c. |

**Sums:** TEST-GAP 58 keys across 21 clusters; EQUIVALENT 22 keys across 8 clusters; LOW-VALUE 20 keys across 4 clusters. 21+8+4 = 33 clusters, 58+22+20 = 100 keys. ✔

## Drafted tests (UNVERIFIED — not yet run red/green)

TDD procedure (same for all): run the drafted test against the mutant copy (`uv run mutmut show` diff applied / mutmut isolated run) → assertion fails (red); run against `backend/services/reid_matcher.py` original → passes (green). Only the serial pytest lane verifies — these were drafted read-only per WP4.3 constraints.

All code below is additive to `backend/tests/unit/services/test_reid_matcher.py`; new imports needed at top: `from sqlalchemy.dialects import postgresql` (existing imports at lines 16-30 otherwise unchanged).

### Helper (shared)

```python
def compile_executed_statement(mock_session: AsyncMock) -> tuple[str, dict]:
    """Compile the statement that was passed to session.execute(), for SQL assertions.

    Style precedent: backend/tests/unit/services/test_search.py:532-592.
    """
    call = mock_session.execute.call_args
    assert call is not None, "service never called session.execute()"
    stmt = call.args[0] if call.args else call.kwargs.get("statement")
    assert stmt is not None, "session.execute() must receive the built statement, not None"
    compiled = stmt.compile(dialect=postgresql.dialect())
    return str(compiled).lower(), dict(compiled.params)
```

### T1 — find_matches SQL shape + cutoff (kills clusters #1 and #2 and #4 — 19 mutants)

```python
class TestFindMatchesQueryContract:
    """Verify the *statement* find_matches builds — mocks otherwise hide every SQL mutation."""

    @pytest.mark.asyncio
    async def test_query_filters_recent_enriched_reid_detections(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Query must filter on time cutoff, non-null enrichment, and reid_embedding key."""
        embedding = create_sample_embedding(seed=1)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await reid_matcher.find_matches(embedding)

        text, params = compile_executed_statement(mock_session)

        assert "from detections" in text
        assert "where" in text
        assert "detections.enrichment_data is not null" in text
        # JSONB key-exists operator '?' applied to 'reid_embedding'
        assert " ? " in text
        assert "reid_embedding" in params.values()
        # Cutoff uses >= so an exactly-at-cutoff detection is included
        assert "detected_at >=" in text

        # The cutoff bind param must be timezone-aware (UTC) and in the past.
        cutoffs = [v for v in params.values() if isinstance(v, datetime)]
        assert len(cutoffs) == 1
        cutoff = cutoffs[0]
        assert cutoff.tzinfo is not None, "cutoff must be timezone-aware"
        assert cutoff < datetime.now(UTC), "cutoff must be now minus the window"
        assert cutoff > datetime.now(UTC) - timedelta(hours=25)

    @pytest.mark.asyncio
    async def test_query_orders_by_recency_desc(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Rows come back newest-first so the DB scan order is deterministic."""
        embedding = create_sample_embedding(seed=1)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await reid_matcher.find_matches(embedding)

        text, _ = compile_executed_statement(mock_session)
        assert "order by detections.detected_at desc" in text
```

### T2 — exclude_detection_id predicate (kills cluster #3 — 4 mutants)

```python
    @pytest.mark.asyncio
    async def test_exclude_detection_id_renders_exclusion_clause(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """exclude_detection_id must add 'id != <id>' — and nothing when omitted."""
        embedding = create_sample_embedding(seed=1)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        # With exclusion
        await reid_matcher.find_matches(embedding, exclude_detection_id=100)
        text, params = compile_executed_statement(mock_session)
        assert "!=" in text, "exclusion must render as 'id != <excluded>'"
        assert 100 in params.values(), "excluded id must be bound as a parameter"

        # Without exclusion: no id predicate at all
        mock_session.execute.reset_mock()
        await reid_matcher.find_matches(embedding)
        text2, _ = compile_executed_statement(mock_session)
        assert "!=" not in text2
```

### T3 — store_embedding lookup + stored payload (kills clusters #17, #20, #21, #22, #23 — 13 mutants)

```python
class TestStoreEmbeddingContract:
    """The lookup must target the right row and the stored payload is a data contract."""

    @pytest.mark.asyncio
    async def test_selects_detection_by_id_and_records_full_metadata(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Query filters by detection id; payload carries full, correct metadata."""
        embedding = create_sample_embedding(seed=1)

        detection = MagicMock(spec=Detection)
        detection.id = 100
        detection.enrichment_data = {}

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = detection
        mock_session.execute.return_value = mock_result

        success = await reid_matcher.store_embedding(100, embedding)
        assert success is True

        # 1) the lookup statement itself
        text, params = compile_executed_statement(mock_session)
        assert "from detections" in text
        assert "detections.id =" in text
        assert "!=" not in text
        assert 100 in params.values()

        # 2) the stored payload — full metadata contract
        payload = detection.enrichment_data["reid_embedding"]
        assert set(payload) == {"vector", "dimension", "hash", "model", "stored_at"}
        assert payload["model"] == "osnet_ain_x1_0"
        assert payload["hash"] == ReIDMatcher._compute_embedding_hash(embedding), (
            "hash must identify the embedding, not a constant/None"
        )
        stored_at = datetime.fromisoformat(payload["stored_at"])
        assert stored_at.tzinfo is not None, "stored_at must be timezone-aware (UTC)"
```

### T4 — cosine math with non-normalized / 1-dim inputs (kills clusters #14 and #16 — 5 mutants)

```python
    # --- added to TestCosineSimilarity ---

    def test_non_normalized_identical_vectors_return_one(self) -> None:
        """[1,2,3] vs itself must be exactly 1.0 — catches exponent and operator flips
        that all-normalized fixtures hide (sum(a²)=1 makes **1.5 indistinguishable)."""
        vec = [1.0, 2.0, 3.0]
        assert ReIDMatcher._cosine_similarity(vec, vec) == pytest.approx(1.0, rel=1e-9)

    def test_non_normalized_opposite_vectors_return_minus_one(self) -> None:
        vec = [1.0, 2.0, 3.0]
        neg = [-v for v in vec]
        assert ReIDMatcher._cosine_similarity(neg, vec) == pytest.approx(-1.0, rel=1e-9)

    def test_single_dimension_vectors_still_computed(self) -> None:
        """1-dim vectors are valid input; only *empty* inputs short-circuit to 0.0."""
        assert ReIDMatcher._cosine_similarity([3.0], [4.0]) == pytest.approx(1.0, rel=1e-9)
        assert ReIDMatcher._cosine_similarity([3.0], [-4.0]) == pytest.approx(-1.0, rel=1e-9)
```

### T5 — scan past bad rows, exact-threshold inclusion, timestamp plumbing (kills clusters #10, #11, #12 — 3 mutants)

```python
    # --- added to TestFindMatches ---

    @pytest.mark.asyncio
    async def test_keeps_scanning_after_embeddingless_detection(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """A detection with no extractable embedding is skipped, not a scan terminator.

        (Existing test_skips_detection_without_embedding places the bad row LAST,
        so continue-vs-break never showed.)
        """
        embedding = create_sample_embedding(seed=1)
        detections = [
            create_mock_detection(detection_id=200, enrichment_data={}),  # bad row FIRST
            create_mock_detection(detection_id=100, reid_embedding=embedding),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = detections
        mock_session.execute.return_value = mock_result

        matches = await reid_matcher.find_matches(embedding)

        assert len(matches) == 1
        assert matches[0].detection_id == 100

    @pytest.mark.asyncio
    async def test_similarity_exactly_at_threshold_is_included(
        self,
        mock_session: AsyncMock,
    ) -> None:
        """'>=' at the boundary must match — [3,4] vs itself is *exactly* 1.0."""
        matcher = ReIDMatcher(session=mock_session, similarity_threshold=1.0)
        detection = create_mock_detection(detection_id=100, reid_embedding=[3.0, 4.0])
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [detection]
        mock_session.execute.return_value = mock_result

        matches = await matcher.find_matches([3.0, 4.0])

        assert len(matches) == 1

    @pytest.mark.asyncio
    async def test_match_carries_detection_timestamp(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """ReIDMatch.timestamp must be the detection's detected_at."""
        embedding = create_sample_embedding(seed=1)
        when = datetime(2026, 9, 1, 12, 0, 0, tzinfo=UTC)
        detection = create_mock_detection(
            detection_id=100, reid_embedding=embedding, detected_at=when
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [detection]
        mock_session.execute.return_value = mock_result

        matches = await reid_matcher.find_matches(embedding)

        assert len(matches) == 1
        assert matches[0].timestamp == when
```

### T6 — embedding extraction guards, grouped elements, factory wiring (kills clusters #13, #32, #33 — 4 mutants)

```python
    # --- added to TestEdgeCases ---

    @pytest.mark.asyncio
    async def test_skips_dict_embedding_without_vector_key(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """A reid_embedding dict without a 'vector' key must be skipped, not crash."""
        embedding = create_sample_embedding(seed=1)
        detection = MagicMock(spec=Detection)
        detection.id = 100
        detection.camera_id = "front_door"
        detection.detected_at = datetime.now(UTC)
        detection.enrichment_data = {"reid_embedding": {"dimension": 512}}  # no 'vector'
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [detection]
        mock_session.execute.return_value = mock_result

        matches = await reid_matcher.find_matches(embedding)
        assert matches == []

    @pytest.mark.asyncio
    async def test_skips_dict_embedding_with_null_vector(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """{"vector": None} must be skipped — must not attempt list(None)."""
        embedding = create_sample_embedding(seed=1)
        detection = MagicMock(spec=Detection)
        detection.id = 100
        detection.camera_id = "front_door"
        detection.detected_at = datetime.now(UTC)
        detection.enrichment_data = {"reid_embedding": {"vector": None}}
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [detection]
        mock_session.execute.return_value = mock_result

        matches = await reid_matcher.find_matches(embedding)
        assert matches == []

    # --- added to TestGetSightingsByCamera ---

    @pytest.mark.asyncio
    async def test_grouped_sightings_contain_match_objects(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """Grouped entries must be the ReIDMatch objects themselves, not placeholders."""
        embedding = create_sample_embedding(seed=1)
        detection = create_mock_detection(detection_id=42, camera_id="porch", reid_embedding=embedding)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [detection]
        mock_session.execute.return_value = mock_result

        by_camera = await reid_matcher.get_sightings_by_camera(embedding)

        assert len(by_camera["porch"]) == 1
        sighting = by_camera["porch"][0]
        assert isinstance(sighting, ReIDMatch)
        assert sighting.detection_id == 42

    # --- added to TestReIDMatcherInit (one added line) ---

    def test_factory_preserves_session(self, mock_session: AsyncMock) -> None:
        """get_reid_matcher must wire the given session into the instance."""
        matcher = get_reid_matcher(mock_session)
        assert matcher.session is mock_session
```

### T7 — wrapper forwarding contracts (kills clusters #29, #30, #31 — 9 mutants; incidentally kills cluster #28's spy-visible kwargs)

```python
class TestWrapperForwarding:
    """is_known_person / get_person_history / get_sightings_by_camera are thin wrappers;
    their forwarded window/limit kwargs are the entire contract."""

    @pytest.mark.asyncio
    async def test_is_known_person_forwards_custom_window(
        self,
        reid_matcher: ReIDMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """time_window_hours=48 must reach the SQL cutoff as ~now-48h, not default 24h."""
        embedding = create_sample_embedding(seed=1)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await reid_matcher.is_known_person(embedding, time_window_hours=48)

        _, params = compile_executed_statement(mock_session)
        cutoff = next(v for v in params.values() if isinstance(v, datetime))
        assert timedelta(hours=47) < (datetime.now(UTC) - cutoff) < timedelta(hours=49)

    @pytest.mark.asyncio
    async def test_get_person_history_forwards_full_window_and_limit(
        self,
        reid_matcher: ReIDMatcher,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """History must forward the caller's window and the documented 100-row cap."""
        seen: dict = {}

        async def fake_find_matches(
            embedding: list[float],
            time_window_hours: int = 0,
            max_results: int = 0,
            **kwargs: object,
        ) -> list[ReIDMatch]:
            seen.update(
                time_window_hours=time_window_hours, max_results=max_results
            )
            return []

        monkeypatch.setattr(reid_matcher, "find_matches", fake_find_matches)
        await reid_matcher.get_person_history([0.1, 0.2], time_window_hours=168)

        assert seen["time_window_hours"] == 168
        assert seen["max_results"] == 100

    @pytest.mark.asyncio
    async def test_get_sightings_by_camera_forwards_full_window_and_limit(
        self,
        reid_matcher: ReIDMatcher,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Grouped sightings must forward window and 100-row cap (else counts truncate at 10)."""
        seen: dict = {}

        async def fake_find_matches(
            embedding: list[float],
            time_window_hours: int = 0,
            max_results: int = 0,
            **kwargs: object,
        ) -> list[ReIDMatch]:
            seen.update(
                time_window_hours=time_window_hours, max_results=max_results
            )
            return []

        monkeypatch.setattr(reid_matcher, "find_matches", fake_find_matches)
        await reid_matcher.get_sightings_by_camera([0.1, 0.2], time_window_hours=12)

        assert seen["time_window_hours"] == 12
        assert seen["max_results"] == 100
```

### Un-killed-by-drafts (remaining TEST-GAP, intentionally low priority)

- Cluster #9 (`find_matches` default `max_results=10`→`11`, 1 key): killable by an 11-detection default-arg test if the team considers the default cap contractual; noted, not drafted.

## Kill tally of the 7 drafted blocks

T1: 19, T2: 4, T3: 13, T4: 5, T5: 3, T6: 4, T7: 9 → **57 of 58** TEST-GAP keys directly killed (T7's spies also exercise cluster #28's kwargs); the remaining 1 (cluster #9) has a one-liner recipe above.

## File:line index

| Item | Location |
|---|---|
| Source under test | `backend/services/reid_matcher.py` (484 lines) |
| Covering test file (only) | `backend/tests/unit/services/test_reid_matcher.py` |
| Weak assertion exemplars | test_reid_matcher.py:411 (`assert mock_session.execute.called`), :514, :532, :701, :754, :771 — "called" checks that let every SQL mutation through |
| Fake boundary test | test_reid_matcher.py:876-900 (`test_exact_threshold_match_included` uses sim=1.0 vs threshold 0.7 — not the boundary) |
| Order-blind skip test | test_reid_matcher.py:465-487 (bad row placed last → `break` invisible) |
| SQL-string assertion style precedent | `backend/tests/unit/services/test_search.py:532-592`; also `test_export_service.py:1447` |
| Meta / verdicts | `mutants/backend/services/reid_matcher.py.meta` |
| Raw diffs (all 100) | `/tmp/wp25/wp44-triage/_rm_all_diffs.txt` |
