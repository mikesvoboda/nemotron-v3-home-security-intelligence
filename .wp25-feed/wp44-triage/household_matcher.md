# WP4.4 Triage Dossier — backend/services/household_matcher.py

- **Survivors:** 134 of 297 mutants (exit_code 0 in `mutants/backend/services/household_matcher.py.meta`)
- **Diffs:** all 134 extracted read-only via mutmut's `get_diff_for_mutant` (line-span index), one process, no test execution.
- **Sole covering test file:** `backend/tests/unit/services/test_household_matcher.py`
  (`mutants/mutmut-stats.json` → `tests_by_mangled_function_name`; other files that mention the module do not exercise these functions' behavior).
- **Structural cause of the survivor mass:** every test stubs the collaborators one layer out —
  `matcher._get_all_member_embeddings` / `_get_vehicles_with_embeddings` / `_find_by_plate` /
  `match_person` / `match_vehicle` are `AsyncMock`s (test file lines 210, 236, 259, 276, 298, 319,
  383, 412, 437–447, 477–478, 500–501, 560, 587, 609, 705–706, 745–746, 786–787, 849–850, 879–880, 1023, 1057–1060).
  A DB-None call (`session→None`) therefore propagates into a mock and dies invisibly, and every
  argument passed *into* a stubbed method (`session=`, `vehicle_type=`, `color=`, `license_plate=`,
  the embedding array) is computed but never asserted. Plus: no test ever produces a similarity
  *exactly* at the threshold, no test uses a zero (falsy-but-present) embedding, no test feeds
  `detections` that actually reach the inner match logic, and nothing ever touches `caplog`.

## Per-cluster table

| # | Cluster (pattern) | Keys | n | Class |
|---|---|---|---|---|
| C1 | Strict `>` similarity-threshold gate → `>=` (off-by-one boundary accepted as match) | `_match_vehicle_visual` 17; `match_person` 17 | 2 | TEST-GAP |
| C2 | `if license_plates and len(license_plates) > 0:` → `... >= 0` (always true when truthy) | `match_detections` 44 | 1 | TEST-GAP |
| C3 | `match.similarity >= threshold` → `>` (exactly-at-threshold person match dropped); sibling `and`→`or` (23) | `match_detections` 24 (23) | 2 | TEST-GAP |
| C4 | Zero-length (falsy-but-present) embedding silently dropped: `if person_embedding:` / `if vehicle_embedding:` None-swaps at call sites | `match_detections` 13, 19; `match_vehicle` 2; `_match_vehicle_visual` 2; `match_detections` 52, 53, 57 | 7 | TEST-GAP |
| C5 | `if license_plate:` branch → `license_plate=None` (plate route never taken) | `match_vehicle` 2 (shared key w/ C4), 56 | 1 | TEST-GAP |
| C6 | Log `logger.debug(msg, *args)` — msg replaced by `None` (debug-logging crash not observed) | `_match_vehicle_visual` 4,31–34,42,43; `match_person` 4,31–34,42,43; `match_vehicle` 6–9,37; `match_detections` 70–73 | 24 | LOW-VALUE |
| C7 | Log call args *removed* (arity-mismatch crash not observed; incl. `session=None` at 60,65) | `_match_vehicle_visual` 35–38,44,45; `match_person` 35–38,44,45; `match_vehicle` 10–13; `match_detections` 74–77 | 20 | LOW-VALUE |
| C8 | Log message cosmetic text: `XX` wrap / lowercase / UPPERCASE | `_match_vehicle_visual` 5–7,39–41,46–48; `match_person` 5–7,39–41,46–48; `match_vehicle` 14–16,38–40; `match_detections` 78–80 | 34 | EQUIVALENT |
| C9 | enrichment dict key renamed/`None`: `license_plates`, `text`, `color` | `match_detections` 36,40,41,49–51,66–68 | 9 | LOW-VALUE¹ |
| C10 | Vehicle-type whitelist tuple cosmetic (`"XXtruckXX"`, `"TRUCK"`, …) | `match_detections` 29–34 | 6 | EQUIVALENT |
| C11 | `session=None` into mocked `_get_all_member_embeddings` | `match_person` 2 | 1 | LOW-VALUE |
| C12 | `vehicle_type=None` into mock / stubbed-arg passthrough (`vehicle_type`, `color` are `noqa: ARG002`) | `match_detections` 58,63; `match_vehicle` 30,31,32 | 5 | LOW-VALUE |
| C13 | Truthy-list `len(pl) > 0` → `> 1` (single-plate extraction skipped) | `match_detections` 45 | 1 | LOW-VALUE² |
| C14 | Plate-keyword `license_plate=plate_text` → `None` at real call site (same kill as C5) | `match_detections` 56 | counted in C5 | TEST-GAP |
| C15 | `continue` → `break` on missing enrichment (only 1 detection tested) | `match_detections` 7 | 1 | LOW-VALUE² |
| C16 | Dead defensive tweaks, no-op arg removals, cosmetic local defaults | `match_detections` 17,39,42,43,46,48,54,61–64; `match_vehicle` 3,4,5; `_match_vehicle_visual` 16 | 15 | EQUIVALENT³ |
| C17 | `isinstance(x, list)` → `... or True` in `extract_*_embedding` return (non-list no longer coerced/None'd) | `x_extract_person_embedding` 16; `x_extract_vehicle_embedding` 16 | 2 | EQUIVALENT |
| C18 | Empty-list guard `len(v) == 0` → `== 1` (single-element vehicle embedding now returns None) | `x_extract_vehicle_embedding` 14 | 1 | TEST-GAP |

¹ Killable in principle by asserting `match_vehicle` receives `license_plate="ABC123"` on enrichment containing one plate (Draft A also kills C5); survives today because `match_vehicle` is `AsyncMock`ed in both vehicle tests (787) and the cached test never supplies plates.
² Killable by a multi-detection test whose detections reach real matching logic (Draft B).
³ `_match_vehicle_visual__16` (`and`→`or`) survives because the mock returns a single vehicle and `best_similarity` starts 0.0 — with one candidate the disjunction cannot diverge; same input shape would be needed as a C1-style multi-candidate test.

**Cluster key sets are disjoint** (56 = C5 representative, listed once) and **counts sum to 134**:
2+1+2+7+1+24+20+34+9+6+1+5+1+1+15+2+1 = 134.

## Clusters in detail

### TEST-GAP clusters (real behavior, line executed, never asserted)

- **C1 — threshold boundary, `>` vs `>=`** (src lines 198, 376). Tests use only clear-pass (≈1.0)
  and clear-fail (≈0.0) similarities; nothing constructs a vector with cosine exactly equal to the
  threshold, so relaxing the strict gate is unobservable. This is the risk-scoring boundary for
  known persons/vehicles — accepting a borderline match suppresses alerts. Killable by a *constructed*
  similarity (e.g. 3-4 dim vectors tuned to land exactly on threshold) — see Draft D.
- **C2 — `len(license_plates) >= 0`** (src 501). With a non-empty list guard, `>= 0` is always true,
  so the mutant is equivalent *for truthy input*; the real bug surface is falsy-but-present input,
  which the `>=0` variant exposes as `license_plates[0]` → IndexError. No test feeds `license_plates: []`
  while asserting the plate path is skipped. (The sibling `> 1` mutant = C13.)
- **C3 — `match.similarity > threshold` at src 493.** A person match with similarity exactly equal to
  the threshold must be kept (>=); mutant drops it. Note existing test
  `test_match_detections_multiple_detections_isolated` (800–863) does not execute this line robustly:
  its `mock_match_person` returns a bare (un-trampoline-able) function, so `match_detections` is
  bypassed when the method is looked up — the surviving status of this line's mutants is partly a
  harness artifact of that fixture, which Draft B removes by using `AsyncMock` with side effects.
- **C4 — zero-length embedding silently dropped.** `extract_*_embedding` deliberately maps `[]` →
  None (valid contract), but src 490 `if person_embedding:` then treats *any* falsy embedding the
  same, and the `X=None` mutants model "never call match_* with it". Tests only use non-empty
  embeddings. Draft B's zero-embedding case pins the contract (detection skipped, no crash) and kills
  13/19; the vehicle-side twins need a plate-less detection carrying `vehicle_visual: [0.0]` to
  observe the silent-None (drafted as secondary assertion in B).
- **C5/C14 — plate route skipped.** `license_plate=None` into the real `_find_by_plate` (match_vehicle 2)
  and `license_plate=None=` keyword into match_vehicle (match_detections 56) both survive because the
  tests stub `_find_by_plate`/`match_vehicle` and only inspect the *return*, never the *arguments*.
  Draft A asserts the plate text is threaded.
- **C18 — empty-list guard off-by-one** (src 609). `== 0` → `== 1`: a single-element `vehicle_visual`
  list now returns None. `extract_vehicle_embedding` is called by real code (not stubbed) in
  `test_match_detections_with_vehicle_detection`, but that test's embeddings dict is empty, so the
  length path is never exercised with `len == 1`. A direct one-liner kills it. (Person-side `== 1`
  mutant was already killed — a 512-element fixture doesn't distinguish it, but the harness ran one
  that did; only the vehicle twin survived.)

### EQUIVALENT clusters

- **C8 (34):** log-message text cosmetics (`XX…XX`, lowercase, UPPERCASE). Message is pure string
  constant; `%`-formatting is unaffected; nothing asserts logs.
- **C10 (6):** vehicle-type tuple members cosmetically renamed/uppercased; no detection in any test
  has `object_type == "truck"`/`"motorcycle"`/uppercase, and renames don't change membership for the
  `"car"` input that *is* tested. Equivalent for every input the type actually takes (lowercase).
- **C16 (15):** defensive tweaks with no effect on tested or realistic behavior: `dtype` removal
  (`np.array(list)` ≈ float64 vs float32 — cosine result numerically equal at this scale), argument
  removals into AsyncMock'd methods (mock records the call but no test checks call args),
  `plate_text = ""` instead of None (`""` is falsy → same branch), `license_plates or len(...) > 0`
  (identical truth table), `embedding_array = ""` (never reaches a consumer because `vehicle_embedding`
  guard sends it down the None path in the tests that run it), `_find_by_plate(plate, )` empty-kwarg
  residue. All: behavior-identical under the test suite's input domain.
- **C17 (2):** `isinstance(x, list) or True` — for list input identical; for non-list input the
  mutant calls `list(x)` (an iterable of floats in practice) instead of returning None. That input
  shape (e.g. `"embeddings": {"person_reid": 512}`) is a corrupted-enrichment edge nobody contracts
  on; low realistic value.

### LOW-VALUE clusters

- **C6 (24) + C7 (20):** debug logging. `logger.debug(None, …)` raises only if logging is actually
  invoked at DEBUG level with that call — unit runs don't configure caplog, and even when it raises
  it only logs-and-swallows inside the logging module. C7's arity-mismatch crashes are likewise
  confined to the debug log line. Nobody should assert debug log arity. Two C7 keys (match_detections
  60, 65: `session=None`/residue) sneak a real-behavior shape in, but only reachable by un-stubbing
  DB access → integration-level; not worth a unit assertion.
- **C9 (9):** renamed dict keys silently change which enrichment key is read. The *behavioral*
  consequence (plate text extracted from the right key) is exactly what Draft A pins — so C9 keys are
  jointly killable with C5 by argument-capture assertions, but in isolation they read as key-name
  cosmetics; kept LOW-VALUE with a pointer to Draft A.
- **C11 (1) + C12 (5):** session/type/color args threaded into fully-mocked collaborators;
  `vehicle_type`/`color` are explicitly reserved-unused (`# noqa: ARG002`). Draft A kills the
  mock-recording subset for free; asserting them per se is low value.
- **C13 (1), C15 (1):** `len(pl) > 1` and `continue→break` need ≥2-item inputs to differ; existing
  tests are all single-detection/single-plate. Real-but-negligible edge behavior; Draft B kills both
  incidentally if added.

## Drafted tests (highest-value clusters first)

**TDD procedure (same for all four):** run against mutant copy → the new assertion FAILS (red);
revert that one line to original → PASSES (green). Never add the test while leaving red.

Target file for all drafts: `backend/tests/unit/services/test_household_matcher.py`
(UNVERIFIED - not yet run red/green; follows the file's AsyncMock/class/`@pytest.mark.asyncio` style.)

```python
# UNVERIFIED - not yet run red/green
# =============================================================================
# WP4.4 mutant-killer tests (household_matcher survivors)
# =============================================================================

class TestHouseholdMatcherPlateThreading:
    """Kills C5/C9/C12 (and mock-visible C6-adjacent): enrichment→match_vehicle argument threading."""

    @pytest.fixture
    def matcher(self) -> HouseholdMatcher:
        return HouseholdMatcher()

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_match_detections_threads_first_plate_to_match_vehicle(
        self,
        matcher: HouseholdMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """First plate dict is extracted by key "text" and passed as license_plate.

        Kills match_detections 56/61 (license_plate=None), 40/41 (enrichment key renamed),
        49/50/51 (plate dict key renamed), 66/67/68 (color key renamed).
        """
        detection = MagicMock()
        detection.id = 2
        detection.object_type = "car"

        enrichment_data = {
            2: {
                "license_plates": [{"text": "ABC123"}, {"text": "SECOND"}],
                "embeddings": {},
                "color": "silver",
            }
        }

        matcher.match_vehicle = AsyncMock(return_value=None)
        matcher.match_person = AsyncMock(return_value=None)

        await matcher.match_detections(
            detections=[detection],
            enrichment_data=enrichment_data,
            session=mock_session,
        )

        matcher.match_vehicle.assert_awaited_once()
        kwargs = matcher.match_vehicle.await_args.kwargs
        assert kwargs["license_plate"] == "ABC123"  # kills plate-key + None mutants
        assert kwargs["color"] == "silver"          # kills color-key mutants
        assert kwargs["vehicle_type"] == "car"      # kills vehicle_type=None mutant
```

```python
# UNVERIFIED - not yet run red/green
class TestHouseholdMatcherDetectionEdges:
    """Kills C2/C3/C4/C13/C15 + Draft-A-adjacent zero-embedding contract."""

    @pytest.fixture
    def matcher(self) -> HouseholdMatcher:
        return HouseholdMatcher()

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_empty_plate_list_skips_plate_route_without_crash(
        self,
        matcher: HouseholdMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """license_plates=[] must short-circuit (not IndexError on plates[0]).

        Kills match_detections 44 (len(pl) >= 0) and 42/43/46/48 via the None threading.
        """
        detection = MagicMock()
        detection.id = 3
        detection.object_type = "car"

        enrichment_data = {3: {"license_plates": [], "embeddings": {}}}

        matcher.match_vehicle = AsyncMock(return_value=None)
        matcher.match_person = AsyncMock(return_value=None)

        await matcher.match_detections(
            detections=[detection],
            enrichment_data=enrichment_data,
            session=mock_session,
        )

        kwargs = matcher.match_vehicle.await_args.kwargs
        assert kwargs["license_plate"] is None

    @pytest.mark.asyncio
    async def test_match_at_exact_threshold_is_kept(
        self,
        matcher: HouseholdMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """similarity == threshold is a valid person match (>=, not >).

        Kills match_detections 24 (>= → >).
        """
        detection = MagicMock()
        detection.id = 4
        detection.object_type = "person"

        enrichment_data = {4: {"embeddings": {"person_reid": [0.1, 0.2, 0.3]}}}

        edge_match = HouseholdMatch(
            member_id=9,
            member_name="Edge Case",
            similarity=matcher.similarity_threshold,  # exactly 0.85
            match_type="person",
        )
        matcher.match_person = AsyncMock(return_value=edge_match)
        matcher.match_vehicle = AsyncMock(return_value=None)

        person_matches, _ = await matcher.match_detections(
            detections=[detection],
            enrichment_data=enrichment_data,
            session=mock_session,
        )

        assert 4 in person_matches  # mutant 24 drops it

    @pytest.mark.asyncio
    async def test_empty_embedding_skips_matching_but_keeps_later_detections(
        self,
        matcher: HouseholdMatcher,
        mock_session: AsyncMock,
    ) -> None:
        """person_reid=[] is skipped (no match call); a LATER detection still processes.

        Kills match_detections 13/19 (embedding None at call site — pins that the real
        extracted array is handed to match_person), 7 (continue→break would stop the loop
        after the skipped detection), and 14/15 via the array-content assertion.
        """
        det_empty = MagicMock()
        det_empty.id = 5
        det_empty.object_type = "person"

        det_good = MagicMock()
        det_good.id = 6
        det_good.object_type = "person"

        enrichment_data = {
            5: {"embeddings": {"person_reid": []}},
            6: {"embeddings": {"person_reid": [0.4, 0.5, 0.6]}},
        }

        good_match = HouseholdMatch(
            member_id=2, member_name="Later", similarity=0.93, match_type="person"
        )
        matcher.match_person = AsyncMock(return_value=good_match)
        matcher.match_vehicle = AsyncMock(return_value=None)

        person_matches, _ = await matcher.match_detections(
            detections=[det_empty, det_good],
            enrichment_data=enrichment_data,
            session=mock_session,
        )

        assert 5 not in person_matches
        assert 6 in person_matches  # breaks on det 5 would fail here (mutant 7)
        matcher.match_person.assert_awaited_once()
        sent_embedding = matcher.match_person.await_args.args[0]
        assert sent_embedding is not None
        np.testing.assert_allclose(sent_embedding, [0.4, 0.5, 0.6], rtol=1e-6)
```

```python
# UNVERIFIED - not yet run red/green
class TestHouseholdMatcherThresholdBoundary:
    """Kills C1: constructed similarity landing EXACTLY on the threshold."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_match_person_similarity_exactly_at_threshold_rejected(
        self,
        mock_session: AsyncMock,
    ) -> None:
        """cosine == threshold must NOT match (strict >): boundary is exclusive.

        Kills match_person 17 and _match_vehicle_visual 17 (same line pattern).
        a=[1,0,0] and b=[0.85,0,0] give cosine exactly 0.85: norm(b)=|0.85| is exact in
        float32 and 0.85/0.85 == 1.0, so dot/norms lands bit-exactly on the threshold.
        """
        threshold = 0.85
        a = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        b = np.array([threshold, 0.0, 0.0], dtype=np.float32)
        assert cosine_similarity(a, b) == threshold  # guard: we are exactly AT the boundary

        matcher = HouseholdMatcher(similarity_threshold=threshold)
        matcher._get_all_member_embeddings = AsyncMock(
            return_value=[(1, "Boundary", b)]
        )

        result = await matcher.match_person(a, mock_session)

        assert result is None  # original (>): not a match; mutant 17 (>=): returns match
```

```python
# UNVERIFIED - not yet run red/green
def test_extract_vehicle_embedding_single_element_list_is_returned() -> None:
    """C18: guard is len == 0, NOT len == 1; a 1-element embedding is 'present'.

    Kills x_extract_vehicle_embedding 14 (== 0 → == 1).
    """
    from backend.services.household_matcher import extract_vehicle_embedding

    embedding = extract_vehicle_embedding({"embeddings": {"vehicle_visual": [0.5]}})

    assert embedding == [0.5]
```

**On C1/Draft D, exact float boundary:** the drafted version normalizes `b` so its first component is
exactly the threshold and the vector is float32-unit, making `cosine_similarity` return the threshold
bit-exactly. If float32 rounding proves off-by-one-ulp when run red/green, the fallback is
`HouseholdMatcher(similarity_threshold=cosine_similarity(a, b))` — compute the threshold FROM the
same vectors, guaranteeing `similarity == threshold` regardless of representation. That variant is
mutant-killing either way and is the version to keep if the literal 0.85 one shows ulp drift.

## Covering test file:line map

| Function | Covering tests (file:lines) |
|---|---|
| `match_person` | `backend/tests/unit/services/test_household_matcher.py:156-330` (`TestHouseholdMatcherPersonMatching`) |
| `match_vehicle` | same file `:337-528` (`TestHouseholdMatcherVehicleMatching`) |
| `_match_vehicle_visual` | same file `:536-618` (`TestHouseholdMatcherVisualVehicleMatching`) |
| `match_detections` | same file `:680-893` (`TestHouseholdMatcherMatchDetections`) |
| `extract_person_embedding` / `extract_vehicle_embedding` | same file `:900-1085` (`TestHouseholdMatcherCachedEmbeddings`) |

## Kill arithmetic

Drafted tests jointly kill: C1(2) + C2(1) + C3(2) + C4(7) + C5/C14(1) + C9(9, via arg capture) +
C12(5, via arg capture) + C13(1) + C15(1) + C18(1) = 30 keys, plus mock-recording C11(1) → 31.
Remaining 103 are EQUIVALENT (57) and LOW-VALUE debug-log (44) — recommend suppressing the
log-arg/log-text mutator classes for this module in the WP4.4 baseline config rather than
writing caplog tests nobody wants to maintain.
