# WP4.4 Triage Dossier — backend/services/auto_enrollment_service.py

**UNVERIFIED — read-only triage wave. No tests were run; mutants not re-verified red/green.**

- Snapshot: `/tmp/wp25/wp44-triage/meta-frozen.json` (copy of `mutants/backend/services/auto_enrollment_service.py.meta`; live file still being written by the run — 25/251 keys still null, so the survivor set below may grow).
- 251 total mutants: 96 killed, **134 survived**, 25 unchecked.
- Diffs derived from `mutants/backend/services/auto_enrollment_service.py` + `.spans` (mutmut copy is complete for this module; `uv run mutmut show` errors with a cache race → manual span-diff fallback used, as sanctioned).
- Key shorthand: `fn#N` = `backend.services.auto_enrollment_service.<mangled fn>__mutmut_N` (mangled fn e.g. `xǁAutoEnrollmentServiceǁis_duplicate`).
- Source: `backend/services/auto_enrollment_service.py` (607 lines).
- **Covering test file (ALL of them): `backend/tests/unit/services/test_auto_enrollment_service.py` (537 lines).** Per mutmut-stats `tests_by_mangled_function_name`, every function's covering tests live in this one file. Production consumers: `backend/api/routes/face_recognition.py` (~lines 1469–1660, list/approve/reject endpoints) — relevant to cluster 17 below.

## Why so many survive: the test harness shape

Every covering test uses `mock_session = AsyncMock()` with canned `MagicMock()` results
(`test_auto_enrollment_service.py:56-58, 151-153, 258-260, 353-360, 439-441, 482-484`). The session never
executes SQL, so ANY mutation to a `select(...)` statement or to arguments passed into
`session.execute()` / delegates is invisible; and the tests assert `mock_session.add.assert_called_once()`
/ `call_count >= 2` instead of WHAT was added (`:228, :370, :490`). That single harness choice explains
clusters 3, 6, 8, 10, 16, 18, 20 wholesale (70 survivors).

## Cluster table (counts sum to 134)

| #   | Pattern                                                                                                                                                                                                                                                                                        | Fn / concern                                                        | Cnt | Class                  | Example keys                    | Kill / note                                                                                                                                                                                                                                                     |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- | --- | ---------------------- | ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `cosine_similarity` zero-norm guard `or`→`and`/wrong constant; `dot/(na*nb)`→`dot*(na*nb)` / `dot/(na/nb)`                                                                                                                                                                                     | cosine_similarity                                                   | 4   | TEST-GAP               | cosine#5, #9, #11               | Drafted D1. Only two callers (`is_duplicate`) feed near-unit vectors, so the zero-guard and divisor are never exercised on a discriminating input; tests assert only True/False dup outcomes.                                                                   |
| 2   | `should_auto_enroll` quality boundary `>=`→`>`                                                                                                                                                                                                                                                 | should_auto_enroll                                                  | 1   | TEST-GAP               | should_auto_enroll#3            | Tests use 0.92 and 0.5 vs threshold 0.8 (`test:67,83,100-124`) — never exactly 0.8. Appendix one-liner.                                                                                                                                                         |
| 3   | `is_duplicate` stmt/execute arg clobber: `select(FaceEmbedding…)`→`None`/`select(None)`, `execute(stmt)`→`execute(None)`                                                                                                                                                                       | is_duplicate                                                        | 3   | TEST-GAP               | is_duplicate#1, #3, #6          | Drafted D2 (captures `execute` arg, asserts `str(stmt)` contains `face_embeddings`).                                                                                                                                                                            |
| 4   | `is_duplicate` best-match init/tie: `best_person_id=None`→`""` (poisons first comparison to TypeError), `similarity > best`→`>=` (ties steal the match)                                                                                                                                        | is_duplicate                                                        | 2   | TEST-GAP               | is_duplicate#24, #36            | Drafted D2 (identical twin rows for persons 1 and 3 → assert first owner wins).                                                                                                                                                                                 |
| 5   | `is_duplicate` duplicate call `best_similarity >= threshold`→`>`                                                                                                                                                                                                                               | is_duplicate                                                        | 1   | TEST-GAP               | is_duplicate#39                 | Only observable at similarity == threshold. Drafted D2 (sets `similarity_threshold` to the exact `cosine_similarity()` value).                                                                                                                                  |
| 6   | `add_to_queue` `is_duplicate(session, emb)` → `None`-ed / dropped args                                                                                                                                                                                                                         | add_to_queue                                                        | 4   | TEST-GAP               | add_to_queue#2, #3, #5          | Drafted D3 (`assert_called_once_with(session, event.embedding)`). Test patches `is_duplicate` but never checks call args.                                                                                                                                       |
| 7   | `add_to_queue` `EnrollmentCandidate(face_event_id=/embedding=/quality_score=/status=…)` each kwarg `=None` or removed (#8–#15); `session.add(None)`; `refresh(None)` (#16, #17)                                                                                                                | add_to_queue                                                        | 10  | TEST-GAP               | add_to_queue#8, #11, #16        | Drafted D3. Existing test asserts only `add.assert_called_once()` (`test:228`).                                                                                                                                                                                 |
| 8   | `list_pending_candidates` stmt/execute arg clobber (`stmt=None`, `select(None)`, `execute(None)`)                                                                                                                                                                                              | list_pending_candidates                                             | 3   | TEST-GAP               | list_pending#1, #7, #11         | Drafted D4. Its only test asserts the canned mock back (`test:249-265`).                                                                                                                                                                                        |
| 9   | `list_pending_candidates` query semantics: `where(status==PENDING)`→`None`/`!=`, `limit`/`offset`→None, `order_by(…desc())`→None                                                                                                                                                               | list_pending_candidates                                             | 5   | TEST-GAP               | list_pending#2, #8, #4          | Drafted D4 (literal-binds SQL string assertions).                                                                                                                                                                                                               |
| 10  | `auto_enroll` count stmt/execute arg clobber                                                                                                                                                                                                                                                   | auto_enroll                                                         | 4   | TEST-GAP               | auto_enroll#1, #3, #4           | Drafted D5.                                                                                                                                                                                                                                                     |
| 11  | `auto_enroll` naming pipeline: LIKE `"Unknown Person %"` → `XX…XX`/case flips, `where(...)`→None; `scalar() or 0`→`and 0`/`or 1`; name `count+1`→`count-1`/`+2`/None                                                                                                                           | auto_enroll                                                         | 9   | TEST-GAP               | auto_enroll#2, #6, #13, #15     | Drafted D5. Existing test mocks count=5 but asserts nothing about the generated name (`test:470-491`).                                                                                                                                                          |
| 12  | `auto_enroll` `KnownPerson(name=/notes=…)`/`FaceEmbedding(person=/embedding=/quality_score=…)` kwargs →None/removed; `session.add(None)`; `refresh(None)` (#18, #20-#23, #25-#34)                                                                                                              | auto_enroll                                                         | 15  | TEST-GAP               | auto_enroll#20, #27, #33        | Drafted D5. Existing test asserts only `add.call_count == 2` (`test:490`).                                                                                                                                                                                      |
| 13  | `auto_enroll` `is_household_member=False`→`True`/`None` (security: auto-enrolled face must not be trusted)                                                                                                                                                                                     | auto_enroll                                                         | 2   | TEST-GAP               | auto_enroll#19, #24             | Drafted D5 (`person.is_household_member is False`). Highest severity in the file.                                                                                                                                                                               |
| 14  | `process_event` delegate args to `is_duplicate`/`auto_enroll`/`add_to_queue` →None/dropped (3 call sites × 4 mutants)                                                                                                                                                                          | process_event                                                       | 12  | TEST-GAP               | process_event#7, #12, #25       | Drafted D6 (`assert_called_once_with`). Tests patch the delegates (`test:280-324`) but never verify the session/event forwarded.                                                                                                                                |
| 15  | `process_event` result key `"person_name"` → `"XXperson_nameXX"`/`"PERSON_NAME"`                                                                                                                                                                                                               | process_event                                                       | 2   | TEST-GAP               | process_event#22, #23           | Drafted D6 (`result == {...}` exact dict). No in-repo consumer of `process_event` yet (only the docstring) — API contract is in `backend/api/schemas/face_recognition.py:747`.                                                                                  |
| 16  | `approve_candidate` stmt/execute arg clobber across all three lookups (candidate/event/person)                                                                                                                                                                                                 | approve_candidate                                                   | 12  | TEST-GAP               | approve#1, #11, #19             | Drafted D7 (assert every `execute` arg is a real stmt containing the expected table+id WHERE).                                                                                                                                                                  |
| 17  | Lookup identity `WHERE id == x`→`!=` in approve (candidate, face-event, person) and reject lookups                                                                                                                                                                                             | approve_candidate, reject_candidate                                 | 4   | TEST-GAP (integration) | approve#4, approve#13, reject#4 | Not killable with AsyncMock — stmt text still contains the id column. Needs a real-DB test (in-memory aiosqlite session): seeding candidates A,B and approving A must not enroll B. Cheapest fix: an integration test in `backend/tests/integration/services/`. |
| 18  | `approve_candidate` `KnownPerson(name=/is_household_member=)`/`FaceEmbedding(person=/embedding=/quality_score=)` kwargs →None/removed; `add(None)`                                                                                                                                             | approve_candidate                                                   | 13  | TEST-GAP               | approve#29, #34, #41            | Drafted D7. Existing test asserts only `add.call_count >= 2` (`test:370`) / `success` + `person_id` (`test:426-428`).                                                                                                                                           |
| 19  | `approve_candidate` review stamping: `if not name`→`if name` (default-name guard flips), `status=APPROVED`→None, `enrolled_person_id = person.id if person_id else None` → None / `and False` / `or True`, `reviewed_at=datetime.now(UTC)`→None / `now(None)` (naive tz)                       | approve_candidate                                                   | 7   | TEST-GAP               | approve#27, #43, #46            | Drafted D7 (both new-person and existing-person paths; `reviewed_at.tzinfo is not None`). API surfaces these fields (`face_recognition.py:1508,1553`). `#44` (`and False`) is equivalent on the new-person path; killed via the existing-person path assert.    |
| 20  | `reject_candidate` stmt/execute arg clobber                                                                                                                                                                                                                                                    | reject_candidate                                                    | 4   | TEST-GAP               | reject#1, #2, #6                | Drafted D8.                                                                                                                                                                                                                                                     |
| 21  | `reject_candidate` `rejection_reason=reason`→None; `reviewed_at`→None / `now(None)`                                                                                                                                                                                                            | reject_candidate                                                    | 3   | TEST-GAP               | reject#12, #13, #14             | Drafted D8. Existing test asserts status only (`test:431-450`).                                                                                                                                                                                                 |
| 22  | `reset_auto_enrollment_service` sets singleton to `""` instead of `None` — `get_auto_enrollment_service()`'s `is None` check then returns the string as "service"                                                                                                                              | reset (module-level)                                                | 1   | TEST-GAP               | reset#1                         | Appendix. Existing test only checks `service1 is not service2` (`test:507-512`), which passes with the poisoned sentinel.                                                                                                                                       |
| 23  | `logger.info/debug(...)` f-string replaced by `None` (message dropped)                                                                                                                                                                                                                         | is_duplicate#40, add_to_queue#6, #18, auto_enroll#35, reject#9, #15 | 6   | EQUIVALENT             | add_to_queue#6                  | Log text only; no caller/test observes logging (`caplog` unused in this file).                                                                                                                                                                                  |
| 24  | Redundant/dead numeric tweaks in `is_duplicate`: `norm > 0`→`>= 0` / `> 1` and `q/norm`→`q*norm` (query pre-normalization is irrelevant — `cosine_similarity` divides by norms anyway); `best_similarity = -1.0`→`-2.0` (no embedding has sim < -1, and `""` init is covered by #24→cluster 4) | is_duplicate#17, #18, #20, #23                                      | 4   | EQUIVALENT             | is_duplicate#18                 | Pre-scaling cancels inside `cosine_similarity`; init sentinel never changes the argmax.                                                                                                                                                                         |
| 25  | Rejection log-message ternary tweaks: `if reason`→`and False`/`or True`, `""`→`"XXXX"` inside `logger.info`                                                                                                                                                                                    | reject#17, #18, #19                                                 | 3   | LOW-VALUE              | reject#17                       | Real change is only the wording of a log line; nobody should assert on it.                                                                                                                                                                                      |

Sums: TEST-GAP 121 (clusters 1–22), EQUIVALENT 10 (23–24), LOW-VALUE 3 (25) = **134**.

## Drafted tests

All target `backend/tests/unit/services/test_auto_enrollment_service.py`, appended in the existing
classes' style (fixtures `service`, `service_auto_approve`, `mock_session`, `high_quality_event`;
`@pytest.mark.asyncio`; existing imports at `:12-29`, plus `from sqlalchemy.dialects import sqlite` and
`cosine_similarity` added to the module's import block).

**TDD procedure (same for every draft):** apply the cluster's mutant → run the named test → the assertion
fails (red) because the mutant's value/argument/semantics differs; restore the original → test passes
(green). Kill claim is per-mutant: each mutant in the killed cluster flips at least one asserted value.

// UNVERIFIED — not yet run red/green

### D1 — kills cluster 1 (cosine_similarity)

```python
class TestCosineSimilarity:
    """Direct tests for the cosine_similarity helper (was only covered via is_duplicate)."""

    def test_zero_vector_operand_returns_zero(self) -> None:
        """Either operand being zero-length must return 0.0 (the `or` guard), not divide by zero."""
        unit = np.array([3.0, 4.0, 0.0, 0.0], dtype=np.float32)  # |unit| = 5
        zero = np.zeros(4, dtype=np.float32)
        assert cosine_similarity(zero, unit) == 0.0
        assert cosine_similarity(unit, zero) == 0.0

    def test_matches_reference_formula(self) -> None:
        """Result must be dot(a, b) / (|a| * |b|) — not dot*(|a|*|b|) nor dot/(|a|/|b|)."""
        a = np.array([3.0, 4.0, 0.0, 0.0], dtype=np.float32)   # |a| = 5
        b = np.array([12.0, 5.0, 0.0, 0.0], dtype=np.float32)  # |b| = 13, dot = 56
        assert cosine_similarity(a, b) == pytest.approx(56.0 / (5.0 * 13.0))
```

Mutants: #5/#9 crash via `x/0` (norm product zero slips past the mangled guard); #11 gives `56*65`; #16 gives `56/(5/13)`.

### D2 — kills clusters 3, 4, 5 (is_duplicate query + best-match + threshold)

```python
    @staticmethod
    def _stored(vec: np.ndarray, person_id: int) -> MagicMock:
        emb = MagicMock(spec=FaceEmbedding)
        emb.embedding = vec.tobytes()
        emb.person = MagicMock(spec=KnownPerson)
        emb.person.id = person_id
        return emb

    @pytest.mark.asyncio
    async def test_is_duplicate_queries_face_embeddings_table(
        self, service: AutoEnrollmentService, mock_session: AsyncMock
    ) -> None:
        """The lookup must pass a real statement against face_embeddings to session.execute."""
        empty = MagicMock()
        empty.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=empty)
        query = np.zeros(8, dtype=np.float32)

        is_dup, matched = await service.is_duplicate(mock_session, query.tobytes())

        assert (is_dup, matched) == (False, None)
        stmt = mock_session.execute.call_args.args[0]
        assert stmt is not None and "face_embeddings" in str(stmt)

    @pytest.mark.asyncio
    async def test_is_duplicate_keeps_first_owner_on_similarity_tie(
        self, service: AutoEnrollmentService, mock_session: AsyncMock
    ) -> None:
        """Strictly-greater best-match search: an equal-similarity later row must not steal the match."""
        q = np.zeros(512, dtype=np.float32)
        q[0] = 1.0
        near = np.zeros(512, dtype=np.float32)
        near[0] = 0.99
        near[1] = np.sqrt(1 - 0.99**2)
        # Two DIFFERENT persons owning byte-identical (tie) embeddings, plus an orthogonal row.
        rows = [self._stored(near, 1), self._stored(np.eye(512, dtype=np.float32)[7], 2), self._stored(near, 3)]
        result = MagicMock()
        result.scalars.return_value.all.return_value = rows
        mock_session.execute = AsyncMock(return_value=result)

        is_dup, matched = await service.is_duplicate(mock_session, q.tobytes())

        assert is_dup is True
        assert matched == 1  # `similarity >= best` (mutant) would return 3; `best_person_id=""` (mutant) raises TypeError

    @pytest.mark.asyncio
    async def test_is_duplicate_flags_similarity_exactly_at_threshold(
        self, mock_session: AsyncMock
    ) -> None:
        """The contract is best_similarity >= threshold — an exact-threshold match IS a duplicate."""
        q = np.zeros(512, dtype=np.float32)
        q[0] = 1.0
        stored = np.zeros(512, dtype=np.float32)
        stored[0] = 0.9
        stored[1] = np.sqrt(1 - 0.81)
        threshold = cosine_similarity(q, stored)  # exactly the float the implementation will compute
        service = AutoEnrollmentService(similarity_threshold=threshold)

        result = MagicMock()
        result.scalars.return_value.all.return_value = [self._stored(stored, 7)]
        mock_session.execute = AsyncMock(return_value=result)

        is_dup, matched = await service.is_duplicate(mock_session, q.tobytes())

        assert is_dup is True
        assert matched == 7
```

### D3 — kills clusters 6, 7 (add_to_queue)

```python
    @pytest.mark.asyncio
    async def test_add_to_queue_persists_complete_pending_candidate(
        self,
        service: AutoEnrollmentService,
        mock_session: AsyncMock,
        high_quality_event: MagicMock,
    ) -> None:
        """Candidate must carry the event's fields, PENDING status, and be the object added/refreshed."""
        with patch.object(service, "is_duplicate", new_callable=AsyncMock) as mock_is_dup:
            mock_is_dup.return_value = (False, None)
            mock_session.add = MagicMock()
            mock_session.commit = AsyncMock()
            mock_session.refresh = AsyncMock()

            candidate = await service.add_to_queue(mock_session, high_quality_event)

        mock_is_dup.assert_called_once_with(mock_session, high_quality_event.embedding)
        persisted = mock_session.add.call_args.args[0]
        assert isinstance(persisted, EnrollmentCandidate)
        assert candidate is persisted
        assert persisted.face_event_id == high_quality_event.id
        assert persisted.embedding == high_quality_event.embedding
        assert persisted.quality_score == high_quality_event.quality_score
        assert persisted.status == EnrollmentStatus.PENDING.value
        mock_session.commit.assert_awaited_once()
        mock_session.refresh.assert_awaited_once_with(persisted)
```

### D4 — kills clusters 8, 9 (list_pending_candidates)

```python
    @pytest.mark.asyncio
    async def test_list_pending_candidates_query_filters_orders_and_pages(
        self, service: AutoEnrollmentService, mock_session: AsyncMock
    ) -> None:
        """Query must filter status='pending', sort newest-first, and apply limit/offset."""
        empty = MagicMock()
        empty.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=empty)

        await service.list_pending_candidates(mock_session, limit=7, offset=3)

        stmt = mock_session.execute.call_args.args[0]
        assert stmt is not None
        sql = str(stmt.compile(dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True}))
        assert "FROM enrollment_candidates" in sql
        assert "status = 'pending'" in sql  # mutant `!=` renders as "status != 'pending'"
        assert "ORDER BY enrollment_candidates.created_at DESC" in sql
        assert "LIMIT 7" in sql
        assert "OFFSET 3" in sql
```

### D5 — kills clusters 10, 11, 12, 13 (auto_enroll — incl. the trust-default security invariant)

```python
    @pytest.mark.asyncio
    async def test_auto_enroll_numbers_person_from_existing_count_and_stays_untrusted(
        self,
        service: AutoEnrollmentService,
        mock_session: AsyncMock,
        high_quality_event: MagicMock,
    ) -> None:
        """Name = 'Unknown Person N+1' over rows LIKE 'Unknown Person %'; person must be un-household."""
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        count_result = MagicMock()
        count_result.scalar.return_value = 5
        mock_session.execute = AsyncMock(return_value=count_result)

        person = await service.auto_enroll(mock_session, high_quality_event)

        stmt = mock_session.execute.call_args.args[0]
        assert stmt is not None
        sql = str(stmt.compile(dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True}))
        assert "known_persons.name LIKE 'Unknown Person %'" in sql

        person_obj, emb_obj = (c.args[0] for c in mock_session.add.call_args_list)
        assert mock_session.add.call_count == 2
        assert isinstance(person_obj, KnownPerson) and isinstance(emb_obj, FaceEmbedding)
        assert person is person_obj
        assert person_obj.name == "Unknown Person 6"
        assert person_obj.is_household_member is False  # auto-enrolled faces are NOT trusted
        assert person_obj.notes == (
            f"Auto-enrolled from camera {high_quality_event.camera_id} on {high_quality_event.timestamp}"
        )
        assert emb_obj.person is person_obj
        assert emb_obj.embedding == high_quality_event.embedding
        assert emb_obj.quality_score == high_quality_event.quality_score
        mock_session.refresh.assert_awaited_once_with(person_obj)

        # NULL count must fall back to 0 (`scalar() or 0`), giving "Unknown Person 1"
        count_result.scalar.return_value = None
        mock_session.add.reset_mock()
        await service.auto_enroll(mock_session, high_quality_event)
        assert mock_session.add.call_args_list[0].args[0].name == "Unknown Person 1"
```

### D6 — kills clusters 14, 15 (process_event)

```python
    @pytest.mark.asyncio
    async def test_process_event_delegates_with_real_args_and_exact_result_keys(
        self,
        service: AutoEnrollmentService,
        service_auto_approve: AutoEnrollmentService,
        mock_session: AsyncMock,
        high_quality_event: MagicMock,
    ) -> None:
        """Delegates get (session, face_event); result dict keys are a published contract."""
        with patch.object(service_auto_approve, "is_duplicate", new_callable=AsyncMock) as dup, \
             patch.object(service_auto_approve, "auto_enroll", new_callable=AsyncMock) as enroll:
            dup.return_value = (False, None)
            person = MagicMock(spec=KnownPerson)
            person.id, person.name = 1, "Unknown Person 1"
            enroll.return_value = person

            result = await service_auto_approve.process_event(mock_session, high_quality_event)

        dup.assert_called_once_with(mock_session, high_quality_event.embedding)
        enroll.assert_called_once_with(mock_session, high_quality_event)
        assert result == {"action": "enrolled", "person_id": 1, "person_name": "Unknown Person 1"}

        with patch.object(service, "is_duplicate", new_callable=AsyncMock) as dup, \
             patch.object(service, "add_to_queue", new_callable=AsyncMock) as enqueue:
            dup.return_value = (False, None)
            cand = MagicMock(spec=EnrollmentCandidate)
            cand.id = 42
            enqueue.return_value = cand

            result = await service.process_event(mock_session, high_quality_event)

        enqueue.assert_called_once_with(mock_session, high_quality_event)
        assert result == {"action": "queued", "candidate_id": 42}
```

### D7 — kills clusters 16 (minus the 4 WHERE-flips), 18, 19 (approve_candidate)

```python
    @pytest.mark.asyncio
    async def test_approve_candidate_new_person_records_full_review(
        self, service: AutoEnrollmentService, mock_session: AsyncMock
    ) -> None:
        """No person_id: default name 'Person <id>', untrusted person, linked embedding, review stamped."""
        embedding = np.random.rand(512).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)
        candidate = MagicMock()
        candidate.id = 1
        candidate.face_event_id = 100
        candidate.embedding = embedding.tobytes()
        candidate.quality_score = 0.92
        candidate.status = EnrollmentStatus.PENDING.value
        event = MagicMock()
        event.id = 100
        event.matched_person_id = None
        event.is_unknown = True
        r_cand = MagicMock()
        r_cand.scalar_one_or_none.return_value = candidate
        r_event = MagicMock()
        r_event.scalar_one_or_none.return_value = event
        mock_session.execute = AsyncMock(side_effect=[r_cand, r_event])
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        result = await service.approve_candidate(mock_session, candidate_id=1)  # name omitted

        assert result is not None and result["success"] is True
        assert result["person_name"] == "Person 1"  # default-name guard, `if not name` flip fails this
        # every lookup passed a real statement naming its target table + id column
        cand_sql, event_sql = (str(c.args[0]) for c in mock_session.execute.call_args_list)
        assert "enrollment_candidates.id" in cand_sql
        assert "face_detection_events.id" in event_sql
        person_obj, emb_obj = (c.args[0] for c in mock_session.add.call_args_list)
        assert isinstance(person_obj, KnownPerson) and isinstance(emb_obj, FaceEmbedding)
        assert person_obj.name == "Person 1"
        assert person_obj.is_household_member is False
        assert emb_obj.person is person_obj
        assert emb_obj.embedding == candidate.embedding
        assert emb_obj.quality_score == candidate.quality_score
        mock_session.refresh.assert_awaited_once_with(person_obj)
        assert candidate.status == EnrollmentStatus.APPROVED.value
        assert candidate.enrolled_person_id is None  # new-person path links nothing back
        assert candidate.reviewed_at is not None
        assert candidate.reviewed_at.tzinfo is not None  # datetime.now(UTC), not naive now(None)

    @pytest.mark.asyncio
    async def test_approve_candidate_existing_person_stamps_enrolled_person_id(
        self, service: AutoEnrollmentService, mock_session: AsyncMock
    ) -> None:
        """Linking path: enrolled_person_id must record the linked person's id."""
        # Same candidate/event mocks as the test above, plus a person result (id=5);
        # mock_session.execute = AsyncMock(side_effect=[r_cand, r_event, r_person]).
        ...  # (mechanical copy of test_approve_candidate_links_to_existing_person's mocks, test:382-415)
        result = await service.approve_candidate(mock_session, candidate_id=1, person_id=5)
        assert result["success"] is True
        person_sql = str(mock_session.execute.call_args_list[2].args[0])
        assert "known_persons.id" in person_sql
        assert candidate.enrolled_person_id == 5
        assert candidate.status == EnrollmentStatus.APPROVED.value
        assert candidate.reviewed_at is not None and candidate.reviewed_at.tzinfo is not None
```

### D8 — kills clusters 20, 21 (reject_candidate)

```python
    @pytest.mark.asyncio
    async def test_reject_candidate_stamps_reason_and_utc_reviewed_at(
        self, service: AutoEnrollmentService, mock_session: AsyncMock
    ) -> None:
        """Rejection must persist REJECTED + reason + timezone-aware reviewed_at."""
        candidate = MagicMock(spec=EnrollmentCandidate)
        candidate.id = 1
        candidate.status = EnrollmentStatus.PENDING.value
        result_obj = MagicMock()
        result_obj.scalar_one_or_none.return_value = candidate
        mock_session.execute = AsyncMock(return_value=result_obj)
        mock_session.commit = AsyncMock()

        assert await service.reject_candidate(mock_session, candidate_id=1, reason="stranger") is True

        stmt = mock_session.execute.call_args.args[0]
        assert stmt is not None and "enrollment_candidates.id" in str(stmt)
        assert candidate.status == EnrollmentStatus.REJECTED.value
        assert candidate.rejection_reason == "stranger"
        assert candidate.reviewed_at is not None
        assert candidate.reviewed_at.tzinfo is not None
        mock_session.commit.assert_awaited_once()
```

### Appendix one-liners — kill clusters 2 and 22

```python
    def test_should_auto_enroll_accepts_quality_exactly_at_threshold(
        self, service: AutoEnrollmentService
    ) -> None:
        assert service.should_auto_enroll(quality_score=service.quality_threshold, is_unknown=True) is True
```

```python
    def test_reset_leaves_singleton_genuinely_unset(self) -> None:
        get_auto_enrollment_service()
        reset_auto_enrollment_service()
        import backend.services.auto_enrollment_service as mod
        assert mod._auto_enrollment_service is None
        assert isinstance(get_auto_enrollment_service(), AutoEnrollmentService)  # a "" sentinel escapes `is None`
```

## Draft kill coverage

Per-cluster kill tally: D1→C1 (4), D2→C3/C4/C5 (6), D3→C6/C7 (14), D4→C8/C9 (8), D5→C10–C13 (30),
D6→C14/C15 (14), D7→C16/C18/C19 (32), D8→C20/C21 (7), appendix→C2/C22 (2).

D1–D8 + appendix kill **117 of the 121** TEST-GAP survivors. The 4 unkilled are cluster 17
(WHERE `==`→`!=` identity flips) — AsyncMock cannot observe which row a WHERE clause selects; they need
the real-DB integration test described above.

## Notes for WP4.4

- Highest priority: cluster 13 (auto_enroll grants household trust — security), then the harness-shape
  clusters 7/12/18 + 3/8/10/16/20/6/14 (a handful of `call_args` / real-model-capture asserts kill ~70).
- The mock-session harness is the systemic root cause; recommend adopting the "capture what was
  `execute`d/`add`ed" pattern as a house rule for every service module in this sweep.
- 25 mutants of 251 were still unchecked at snapshot time; re-diff the meta when the run finishes —
  expect additions to be operator variants that fold into clusters 1–22.
- All drafted tests: **// UNVERIFIED — not yet run red/green.**
