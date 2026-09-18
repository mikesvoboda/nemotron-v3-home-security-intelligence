# WP4.4 Triage Dossier — `backend/services/unified_embedding_service.py`

**Source of verdicts:** `mutants/backend/services/unified_embedding_service.py.meta` → `exit_code_by_key`
**Snapshot taken:** 2026-09-17, run still in flight (77 keys still `null`).
**Counts at snapshot:** 320 keys total → **125 SURVIVED (exit 0)**, 118 killed, 77 unchecked.
The 77 unchecked may add survivors later; this dossier partitions exactly the 125 recorded survivors.

**Survivors live in 3 functions only:** `propagate_face_match_to_entity` (P, 39), `get_person_sighting_history` (G, 44), `link_face_event_to_entity` (L, 42). No survivors in `get_unified_person_context`, `find_entity_by_face_match`, the private helpers, the dataclasses, or the singleton accessors.

**Covering test file (only one in the whole repo):**
`backend/tests/unit/services/test_unified_embedding_service.py` — 655 lines.
- `TestPropagateFaceMatchToEntity` :239 (3 tests) — main one at **:295 / :296-356**
- `TestGetPersonSightingHistory` :415 (2 tests) — main one at **:449 / :450-524**
- `TestLinkFaceEventToEntity` :527 (3 tests) — main one at **:587 / :588-627**

**Production callers:** none. `grep -rn` across `backend/` + `frontend/` for all three method names returns only this test file. These three methods are currently **public API with zero production use** — the WP4.4 tests below are the *only* thing that will ever guard them, so response-contract assertions carry the whole burden.

---

## Root cause of the whole survivor set

`get_person_sighting_history`/`propagate_...`/`link_...` build SQLAlchemy `select()` objects and hand them to a **fully mocked `session`** (`AsyncMock`). The mock accepts **any** object: `session.execute(None)` returns a canned `MagicMock` and the method never inspects the statement it was handed. So every mutation to the SQL text (WHERE/ORDER BY/LIMIT/args → `None`) executes without error and returns canned rows.

On top of that, the assertions are **presence-only**: `assert "face_match" in entity.entity_metadata` (:355) and `assert len(entity.entity_metadata["face_associations"]) == 1` (:627) and `assert len(result["face_events"]) == 1` (:522). They check that *a* container exists with *n* entries, never that the entries have the contract-specified **keys** or **values**.

That one pattern produces ~110 of the 125 survivors. Both gaps are cheap to close: the mock session has `call_args`/`call_args_list`, so the statement the service actually built is already sitting there, assertions just never read it.

---

## Cluster table (counts sum to 125)

Keys are abbreviated to `<fn>#<n>`; the full key is
`backend.services.unified_embedding_service.xǁUnifiedEmbeddingServiceǁ<fn>__mutmut_<n>`.

| # | Cluster | Func | Count | Class | What mutmut changes | Why it survives / verdict |
|---|---------|------|-------|-------|---------------------|---------------------------|
| 1 | `G-response-dict-keys` | G | 30 | **TEST-GAP** | every response dict key → `"XXkeyXX"` or `"KEY"` | Test asserts `result["household_member"]["trust_level"]` on the *original* spelling, so the renamed key just goes unread; `len(result["face_events"]) == 1` is length-only, so all 5 face-event keys escape. Keys are the API contract. |
| 2 | `G-sql-construction` | G | 12 | **TEST-GAP** | `stmt=None`, `select(None)`, `where(None)`, `limit(None)`, `order_by(None)`, `==`→`!=`, `execute(None)` | Mocked session accepts any object and returns canned rows, so no SQL is ever evaluated. All 12 alter the query semantics (filter/order/limit) that the test never checks. |
| 3 | `L-metadata-dict-keys` | L | 12 | **TEST-GAP** | persisted `face_associations` entry keys → `XX`/UPPER (incl. `.get("XXface_associationsXX")` rewrites at 36/37) | Test only does `in` + `len == 1` (:626-627). Every renamed persisted key survives. |
| 4 | `P-metadata-dict-keys` | P | 8 | **TEST-GAP** | persisted `face_match` block keys → `XX`/UPPER | Test does `assert "face_match" in entity.entity_metadata` (:355) — key of the *outer* dict, so inner key renames are invisible. |
| 5 | `identity-arg-none` | P,G,L | 7 | **TEST-GAP** | `session, face_event_id`→`session, None`; same for `entity_id`, `known_person_id` (P3,P21,P45 / G34,G72 / L3,L9) | Mocked session ignores args; no assertion on `session.execute.call_args`, so the query is not inspected for `WHERE ... = 1` / the `@>` param. |
| 6 | `assoc-field-null` | L,P | 6 | **TEST-GAP** | `known_person_id`/`household_member_id` → `None`, sentinel `""`, `face_confidence=None` | Existing tests assert these fields only with the happy fixture (P) or never (L). The `""` sentinel is a real type violation that no test rejects. |
| 7 | `P-info-log-text` | P | 11 | EQUIVALENT | `logger.info` msg → `XX`/lower/UPPER/`None`/arg-removal | Log text only, no return-state change. |
| 8 | `L-info-log-text` | L | 11 | EQUIVALENT | `logger.info` msg → same | Log text only. |
| 9 | `P-debug-log-text` | P | 7 | EQUIVALENT | `logger.debug` msg → same | Log text only. |
| 10 | `G-ternary-ts-guard` | G | 4 | **TEST-GAP** | `if e.first_seen_at` → `if (e.first_seen_at) and False` / `or True` | 87/91 always emit `None`; 88/92 always `.isoformat()` → `AttributeError` on a NULL timestamp. Fixture always sets a non-null datetime, so the None-branch is never entered. |
| 11 | `confidence-fallback` | P,L | 3 | **TEST-GAP** | `match_confidence or 0.0` → `or 1.0` (P39,L29) / `and 0.0` (L28) | Only truthy confidences are exercised. L's own happy fixture uses `match_confidence = 0.0` — with `and 0.0` that stays 0.0, so L28 is only reachable via a matched-person fixture. |
| 12 | `L-kwargs-removed` | L | 3 | **TEST-GAP** | `known_person_id=`/`household_member_id=`/`face_confidence=` dropped from the dataclass call → dataclass defaults | Result fields silently become `None`/`0.0`; the link test asserts `association_type` and metadata, never these three. |
| 13 | `P-assoc-type-label` | P | 3 | **TEST-GAP** | `association_type="face_match"` → `None`/`XXface_matchXX`/`FACE_MATCH` | `association_type` is never asserted in `test_creates_association_and_updates_entity_trust`. |
| 14 | `metadata-payload-structure` | P,L | 3 | **TEST-GAP** | `entity_metadata["face_match"] = None` (P54); `.get(None, [])` (L32); appended payload `{...}` → `None` (L38) | All destroy the persisted structure; only presence/length is asserted. L32's `get(None,[])` also **silently discards previously linked associations** on every second call. |
| 15 | `G-entity-id-str-none` | G | 1 | **TEST-GAP** | `"id": str(e.id)` → `str(None)` | `result["entities"]` entries never asserted per-field. |
| 16 | `metadata-init-guard` | P,L | 2 | **TEST-GAP** | `if entity.entity_metadata is None:` → `is not None:` | **Latent real bug for the JSONB column**: original initialises a *fresh* dict; mutant leaves `None` and then indexes it → `TypeError`, and the fresh-copy semantics for JSONB change-tracking are lost. Survives only because the fixture pre-sets `entity_metadata = {}`. |
| 17 | `P-assoc-type-default-equal` | P | 1 | **EQUIVALENT** | drops `association_type="face_match"` → dataclass default is already `"face_match"` | Byte-identical behaviour. |
| 18 | `P-or-guard` | P | 1 | **TEST-GAP** | `if update_trust and known_person.is_household_member:` → `or` | Mutant updates trust when `update_trust=False` for a household member, and when a non-household known person is present with `update_trust=True`. Both branches untested. |

**Sum:** 30+12+12+8+7+6+11+11+7+4+3+3+3+3+1+2+1+1 = **125**.
**By class:** TEST-GAP 101, EQUIVALENT 24, LOW-VALUE 0.

### On the 24 EQUIVALENT
All are `logger.debug`/`logger.info` message-text, log-argument, and one dataclass-default-equivalent mutation. Killing these would mean asserting on log output, which is not worth the coupling — leave them. They are 19% of this module's survivors; a per-module score of 125/320 surviving should be read as **the SQL-construction and response-contract dimensions are essentially untested**, not as "a quarter of the module is unkillable noise".

Note `metadata-init-guard` (16): classified TEST-GAP rather than EQUIVALENT because `Entity.entity_metadata` is a `JSONB` column (`backend/models/entity.py:88`), where the `is None` → fresh-`{}` branch is the SQLAlchemy mutable-dict-tracking pattern; the flipped guard would raise `TypeError` in real use. It survives purely due to fixture shape, not because the mutation is harmless.

---

## The 6 drafted tests

All follow the file's existing style (`AsyncMock`/`MagicMock` session, `@pytest.mark.asyncio`, `MagicMock(spec=Model)`). Two new assertions do the heavy lifting across several clusters:

- **Inspect the built statement:** `str(stmt.compile(dialect=postgresql.dialect())).replace(" ", "")` from `mock_session.execute.call_args` — the mock already received the real statement, so this kills `stmt=None` (raises `AttributeError`), `where(None)`/`select(None)` (`WHERE NULL` / no table), `==`→`!=`, `limit(None)`, `order_by(None)`, and every `… , None)` arg mutation (the literal param vanishes). **SQLAlchemy 2.0.53**; `literal_binds=True` is deliberately avoided because JSONB has no literal renderer — bound params come from `q.compile(dialect=postgresql.dialect()).params` instead (both forms probe-verified this session).
- **Assert the response contract structurally:** `set(entry) == {…}` kills *every* `XX`/UPPER key rename in one line, per-field values kill the value mutations.

### TDD procedure (one line)
Add the test, run `uv run pytest backend/tests/unit/services/test_unified_embedding_service.py -k <new_name> -p no:randomly -n0` → expect **FAIL** against the mutant copy; run the same test against the untouched `backend/` → expect **PASS**; then `uv run mutmut run` re-checks only those keys and they flip from survived to killed.

---

```python
# ---------------------------------------------------------------------------
# WP4.4: kill surviving mutants for get_person_sighting_history /
# link_face_event_to_entity / propagate_face_match_to_entity.
# // UNVERIFIED - not yet run red/green
# ---------------------------------------------------------------------------

from sqlalchemy.dialects import postgresql  # uuid/datetime/UTC/AsyncMock/MagicMock already imported at file top


def _sql(mock_session: AsyncMock, call_index: int = 0) -> str:
    """Normalize the SQLAlchemy statement the service handed to session.execute.

    The mocked session accepts any object, so mutations that break or rewire the
    query (stmt=None, where(None), limit(None), == -> !=, arg -> None) are
    invisible unless we inspect what was actually passed. Whitespace is stripped
    so clause-count differences still change the string.
    """
    stmt = mock_session.execute.call_args_list[call_index].args[0]
    compiled = str(stmt.compile(dialect=postgresql.dialect()))
    return " ".join(compiled.split())


def _params(mock_session: AsyncMock, call_index: int = 0) -> dict:
    stmt = mock_session.execute.call_args_list[call_index].args[0]
    return dict(stmt.compile(dialect=postgresql.dialect()).params)


class TestSightingHistoryQueryContract:
    """get_person_sighting_history must build the query the callers rely on.

    Kills clusters: G-sql-construction (12), identity-arg-none on G (2),
    plus G-entity-id-str-none / G-ternary-ts-guard via per-field value asserts.
    """

    @pytest.fixture
    def service(self) -> UnifiedEmbeddingService:
        """Create service instance."""
        return UnifiedEmbeddingService()

    @pytest.mark.asyncio
    async def test_queries_filter_order_and_limit(self, service: UnifiedEmbeddingService) -> None:
        """The face-event query filters by matched person, newest-first, limited."""
        known_person = MagicMock(spec=KnownPerson)
        known_person.id = 10
        known_person.name = "John Doe"
        known_person.is_household_member = True
        known_person.notes = None

        mock_result_person = MagicMock()
        mock_result_person.scalar_one_or_none.return_value = known_person
        mock_result_member = MagicMock()
        mock_result_member.scalar_one_or_none.return_value = None
        mock_result_faces = MagicMock()
        mock_result_faces.scalars.return_value.all.return_value = []
        mock_result_entities = MagicMock()
        mock_result_entities.scalars.return_value.all.return_value = []

        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                mock_result_person,
                mock_result_member,
                mock_result_faces,
                mock_result_entities,
            ]
        )

        await service.get_person_sighting_history(
            session=session,
            known_person_id=10,
            limit=7,
        )

        # call 0: known_persons lookup must target THIS person, not any person
        person_sql = _sql(session, 0)
        assert "known_persons" in person_sql
        assert "NULL" not in person_sql
        assert _params(session, 0) and 10 in _params(session, 0).values()
        assert "!=" not in person_sql

        # call 1: household member lookup on the same known_person_id
        member_sql = _sql(session, 1)
        assert "household_members" in member_sql
        assert "IS NULL" not in member_sql  # mutant passes None -> "IS NULL"
        assert 10 in _params(session, 1).values()

        # call 2: face events -- filter + newest-first + limit
        face_sql = _sql(session, 2)
        assert "face_detection_events" in face_sql
        assert "WHERE NULL" not in face_sql
        assert "!=" not in face_sql
        assert "timestamp DESC" in face_sql
        assert "LIMIT 7" in face_sql  # limit(None) drops the clause entirely
        assert 10 in _params(session, 2).values()

        # call 3: entity lookup must contain THIS person's face_match metadata
        ent_sql = _sql(session, 3)
        assert "@>" in ent_sql
        assert "@<" not in ent_sql
        assert "10" in str(_params(session, 3).values())


class TestSightingHistoryResponseContract:
    """The returned dict is the API contract; keys and values must be exact.

    Kills cluster: G-response-dict-keys (30), G-entity-id-str-none (1),
    G-ternary-ts-guard (4).
    """

    @pytest.fixture
    def service(self) -> UnifiedEmbeddingService:
        """Create service instance."""
        return UnifiedEmbeddingService()

    @staticmethod
    def _fixtures() -> tuple:
        known_person = MagicMock(spec=KnownPerson)
        known_person.id = 10
        known_person.name = "John Doe"
        known_person.is_household_member = True
        known_person.notes = "Test person"

        household_member = MagicMock(spec=HouseholdMember)
        household_member.id = 5
        household_member.name = "John Doe"
        household_member.role = MemberRole.RESIDENT
        household_member.trusted_level = TrustLevel.FULL

        face_event = MagicMock(spec=FaceDetectionEvent)
        face_event.id = 1
        face_event.camera_id = "front_door"
        face_event.timestamp = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
        face_event.match_confidence = 0.95
        face_event.quality_score = 0.8

        entity = MagicMock(spec=Entity)
        entity.id = uuid.UUID("00000000-0000-0000-0000-000000000007")
        entity.entity_type = "person"
        entity.trust_status = TrustStatus.TRUSTED.value
        entity.first_seen_at = datetime(2026, 9, 16, 8, 0, tzinfo=UTC)
        entity.last_seen_at = datetime(2026, 9, 17, 9, 30, tzinfo=UTC)
        entity.detection_count = 5
        return known_person, household_member, face_event, entity

    @pytest.mark.asyncio
    async def test_response_shape_is_exact(self, service: UnifiedEmbeddingService) -> None:
        """Every response key name and value is part of the contract."""
        known_person, household_member, face_event, entity = self._fixtures()

        r_person, r_member, r_faces, r_entities = (MagicMock() for _ in range(4))
        r_person.scalar_one_or_none.return_value = known_person
        r_member.scalar_one_or_none.return_value = household_member
        r_faces.scalars.return_value.all.return_value = [face_event]
        r_entities.scalars.return_value.all.return_value = [entity]

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[r_person, r_member, r_faces, r_entities])

        result = await service.get_person_sighting_history(
            session=session,
            known_person_id=10,
        )

        assert set(result) == {
            "known_person",
            "household_member",
            "face_events",
            "entities",
            "total_sightings",
        }

        kp = result["known_person"]
        assert set(kp) == {"id", "name", "is_household_member", "notes"}
        assert kp["id"] == 10
        assert kp["name"] == "John Doe"
        assert kp["is_household_member"] is True
        assert kp["notes"] == "Test person"

        hm = result["household_member"]
        assert set(hm) == {"id", "name", "role", "trust_level"}
        assert hm["id"] == 5
        assert hm["role"] == "resident"
        assert hm["trust_level"] == "full"

        fe = result["face_events"]
        assert len(fe) == 1
        assert set(fe[0]) == {
            "id",
            "camera_id",
            "timestamp",
            "confidence",
            "quality_score",
        }
        assert fe[0]["id"] == 1
        assert fe[0]["camera_id"] == "front_door"
        assert fe[0]["timestamp"] == "2026-09-17T12:00:00+00:00"
        assert fe[0]["confidence"] == 0.95
        assert fe[0]["quality_score"] == 0.8

        ent = result["entities"]
        assert len(ent) == 1
        assert set(ent[0]) == {
            "id",
            "entity_type",
            "trust_status",
            "first_seen_at",
            "last_seen_at",
            "detection_count",
        }
        # str(e.id) -> str(None) and both ternary short-circuits die here
        assert ent[0]["id"] == "00000000-0000-0000-0000-000000000007"
        assert ent[0]["first_seen_at"] == "2026-09-16T08:00:00+00:00"
        assert ent[0]["last_seen_at"] == "2026-09-17T09:30:00+00:00"
        assert ent[0]["detection_count"] == 5
        assert result["total_sightings"] == 6

    @pytest.mark.asyncio
    async def test_null_first_seen_yields_none(
        self,
        service: UnifiedEmbeddingService,
    ) -> None:
        """A NULL first_seen_at must serialize as None, not crash or lie.

        Kills get_person_sighting_history#88/#92 (`or True` -> unconditional
        .isoformat() -> AttributeError) and #87/#91 (`and False`, covered by the
        complementary non-null case above).
        """
        known_person, _hm, _fe, entity = self._fixtures()
        entity.first_seen_at = None
        entity.last_seen_at = None

        r_person, r_member, r_faces, r_entities = (MagicMock() for _ in range(4))
        r_person.scalar_one_or_none.return_value = known_person
        r_member.scalar_one_or_none.return_value = None
        r_faces.scalars.return_value.all.return_value = []
        r_entities.scalars.return_value.all.return_value = [entity]

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[r_person, r_member, r_faces, r_entities])

        result = await service.get_person_sighting_history(
            session=session,
            known_person_id=10,
        )

        assert result["entities"][0]["first_seen_at"] is None
        assert result["entities"][0]["last_seen_at"] is None


class TestLinkAssociationContract:
    """link_face_event_to_entity must persist a complete association record.

    Kills clusters: L-metadata-dict-keys (12), L-kwargs-removed (3),
    metadata-payload-structure L32/L38, assoc-field-null on L,
    identity-arg-none on L (2).
    """

    @pytest.fixture
    def service(self) -> UnifiedEmbeddingService:
        """Create service instance."""
        return UnifiedEmbeddingService()

    @pytest.mark.asyncio
    async def test_association_fields_and_metadata_entry_are_exact(
        self,
        service: UnifiedEmbeddingService,
    ) -> None:
        """Association fields carry the real ids; metadata entry has exact keys."""
        entity_id = uuid.uuid7()

        known_person_id = 10
        face_event = MagicMock(spec=FaceDetectionEvent)
        face_event.id = 1
        face_event.match_confidence = 0.95
        face_event.matched_person_id = known_person_id

        household_member = MagicMock(spec=HouseholdMember)
        household_member.id = 5

        entity = MagicMock(spec=Entity)
        entity.id = entity_id
        entity.entity_metadata = {}

        r_face, r_member, r_entity = (MagicMock() for _ in range(3))
        r_face.scalar_one_or_none.return_value = face_event
        r_member.scalar_one_or_none.return_value = household_member
        r_entity.scalar_one_or_none.return_value = entity

        session = AsyncMock()
        session.flush = AsyncMock()
        session.execute = AsyncMock(side_effect=[r_face, r_member, r_entity])

        result = await service.link_face_event_to_entity(
            session=session,
            face_event_id=1,
            entity_id=entity_id,
            association_type="manual",
        )

        assert result is not None
        assert result.face_event_id == 1
        assert result.entity_id == entity_id
        # kwargs removed (mutmut_24/25/26) -> dataclass defaults -> these fail
        assert result.known_person_id == known_person_id
        assert result.household_member_id == 5
        assert result.face_confidence == 0.95
        assert result.association_type == "manual"

        entry = entity.entity_metadata["face_associations"][0]
        assert set(entry) == {
            "face_event_id",
            "known_person_id",
            "confidence",
            "type",
            "linked_at",
        }
        assert entry["face_event_id"] == 1
        assert entry["known_person_id"] == known_person_id
        assert entry["confidence"] == 0.95
        assert entry["type"] == "manual"
        assert entry["linked_at"] == result.created_at.isoformat()

        # lookups targeted the real ids, not None
        assert 1 in _params(session, 0).values()
        assert known_person_id in _params(session, 1).values()
        assert "IS NULL" not in _sql(session, 1)
        assert str(entity_id) in _params(session, 2).values()

    @pytest.mark.asyncio
    async def test_existing_associations_are_preserved(
        self,
        service: UnifiedEmbeddingService,
    ) -> None:
        """A second link appends; it never drops previously stored links.

        Kills link_face_event_to_entity#32 -- entity_metadata.get(None, [])
        always starts a fresh list, and the write-back silently discards the
        earlier associations.
        """
        entity_id = uuid.uuid7()

        face_event = MagicMock(spec=FaceDetectionEvent)
        face_event.id = 2
        face_event.match_confidence = 0.4
        face_event.matched_person_id = None

        entity = MagicMock(spec=Entity)
        entity.id = entity_id
        entity.entity_metadata = {
            "face_associations": [{"face_event_id": 1, "type": "manual"}],
        }

        r_face, r_entity = (MagicMock() for _ in range(2))
        r_face.scalar_one_or_none.return_value = face_event
        r_entity.scalar_one_or_none.return_value = entity

        session = AsyncMock()
        session.flush = AsyncMock()
        session.execute = AsyncMock(side_effect=[r_face, r_entity])

        await service.link_face_event_to_entity(
            session=session,
            face_event_id=2,
            entity_id=entity_id,
        )

        assoc = entity.entity_metadata["face_associations"]
        assert len(assoc) == 2
        assert assoc[0]["face_event_id"] == 1
        assert assoc[1]["face_event_id"] == 2


class TestPropagateAssociationContract:
    """propagate_face_match_to_entity: persisted block + trust-decision branches.

    Kills clusters: P-metadata-dict-keys (8), P-assoc-type-label (3),
    identity-arg-none on P (3), assoc-field-null on P (1),
    metadata-payload-structure P54, P-or-guard (1), confidence-fallback (P39).
    """

    @pytest.fixture
    def service(self) -> UnifiedEmbeddingService:
        """Create service instance."""
        return UnifiedEmbeddingService()

    @staticmethod
    def _session(
        face_event: MagicMock,
        household_member: MagicMock | None,
        entity: MagicMock,
    ) -> AsyncMock:
        r_face, r_member, r_entity = (MagicMock() for _ in range(3))
        r_face.scalar_one_or_none.return_value = face_event
        r_member.scalar_one_or_none.return_value = household_member
        r_entity.scalar_one_or_none.return_value = entity
        session = AsyncMock()
        session.flush = AsyncMock()
        session.execute = AsyncMock(side_effect=[r_face, r_member, r_entity])
        return session

    @pytest.mark.asyncio
    async def test_face_match_metadata_block_is_exact(self) -> None:
        """The face_match block keys/values are the contract find_entity_by_face_match reads."""
        service = UnifiedEmbeddingService()
        entity_id = uuid.uuid7()

        known_person = MagicMock(spec=KnownPerson)
        known_person.id = 10
        known_person.name = "John Doe"
        known_person.is_household_member = True

        face_event = MagicMock(spec=FaceDetectionEvent)
        face_event.id = 1
        face_event.match_confidence = 0.95
        face_event.matched_person = known_person

        entity = MagicMock(spec=Entity)
        entity.id = entity_id
        entity.entity_metadata = {}
        entity.trust_status = TrustStatus.UNKNOWN.value

        household_member = MagicMock(spec=HouseholdMember)
        household_member.id = 5
        household_member.trusted_level = TrustLevel.FULL

        session = self._session(face_event, household_member, entity)

        result = await service.propagate_face_match_to_entity(
            session=session,
            face_event_id=1,
            entity_id=entity_id,
        )

        assert result is not None
        assert result.association_type == "face_match"  # P31/37/40/41
        assert result.known_person_id == 10
        assert result.household_member_id == 5
        assert result.face_confidence == 0.95

        block = entity.entity_metadata["face_match"]
        assert set(block) == {
            "known_person_id",
            "known_person_name",
            "face_confidence",
            "matched_at",
        }
        assert block["known_person_id"] == 10
        assert block["known_person_name"] == "John Doe"
        assert block["face_confidence"] == 0.95
        assert block["matched_at"] == result.created_at.isoformat()

        assert 1 in _params(session, 0).values()
        assert 10 in _params(session, 1).values()
        assert str(entity_id) in _params(session, 2).values()

    @pytest.mark.asyncio
    async def test_update_trust_false_leaves_trust_untouched(self) -> None:
        """update_trust=False must not change entity trust.

        Kills propagate_face_match_to_entity#42 (`and` -> `or`), which trusts
        the entity whenever the person is a household member, flag or not.
        """
        service = UnifiedEmbeddingService()
        entity_id = uuid.uuid7()

        known_person = MagicMock(spec=KnownPerson)
        known_person.id = 10
        known_person.name = "John Doe"
        known_person.is_household_member = True

        face_event = MagicMock(spec=FaceDetectionEvent)
        face_event.id = 1
        face_event.match_confidence = 0.95
        face_event.matched_person = known_person

        entity = MagicMock(spec=Entity)
        entity.id = entity_id
        entity.entity_metadata = {}
        entity.trust_status = TrustStatus.UNKNOWN.value

        household_member = MagicMock(spec=HouseholdMember)
        household_member.id = 5
        household_member.trusted_level = TrustLevel.FULL

        session = self._session(face_event, household_member, entity)

        await service.propagate_face_match_to_entity(
            session=session,
            face_event_id=1,
            entity_id=entity_id,
            update_trust=False,
        )

        assert entity.trust_status == TrustStatus.UNKNOWN.value
        assert "face_match" not in entity.entity_metadata

    @pytest.mark.asyncio
    async def test_null_confidence_falls_back_to_zero(self) -> None:
        """A NULL match_confidence must land as 0.0, never 1.0.

        Kills propagate_face_match_to_entity#39 and link_face_event_to_entity#29
        (`or 0.0` -> `or 1.0`) and link#28 (`or` -> `and`), none of which the
        truthy-confidence fixtures can observe.
        """
        service = UnifiedEmbeddingService()
        entity_id = uuid.uuid7()

        known_person = MagicMock(spec=KnownPerson)
        known_person.id = 10
        known_person.name = "John Doe"
        known_person.is_household_member = False  # no trust write needed

        face_event = MagicMock(spec=FaceDetectionEvent)
        face_event.id = 1
        face_event.match_confidence = None
        face_event.matched_person = known_person

        entity = MagicMock(spec=Entity)
        entity.id = entity_id
        entity.entity_metadata = {}

        session = self._session(face_event, None, entity)

        result = await service.propagate_face_match_to_entity(
            session=session,
            face_event_id=1,
            entity_id=entity_id,
        )

        assert result is not None
        assert result.face_confidence == 0.0
```

---

## Drafted-test → cluster kill map

| Drafted test | Clusters killed | Keys |
|---|---|---|
| `TestSightingHistoryQueryContract.test_queries_filter_order_and_limit` | G-sql-construction (12), identity-arg-none on G (2) | G13,14,15,16,18,48,49,50,51,52,53,55; G34,72 |
| `TestSightingHistoryResponseContract.test_response_shape_is_exact` | G-response-dict-keys (30), G-entity-id-str-none (1) | G4,5,28-31,42-45,60-69,78-86,89,90; G80 |
| `TestSightingHistoryResponseContract.test_null_first_seen_yields_none` | G-ternary-ts-guard (4) | G87,88,91,92 |
| `TestLinkAssociationContract.test_association_fields_and_metadata_entry_are_exact` | L-metadata-dict-keys (12), L-kwargs-removed (3), assoc-field-null on L (5), metadata-payload-structure L38, identity-arg-none on L (2) | L36,37,39-48; L24,25,26; L13,14,18,19,20; L38; L3,9 |
| `TestLinkAssociationContract.test_existing_associations_are_preserved` | metadata-payload-structure L32, metadata-init-guard L30 | L32, L30 |
| `TestPropagateAssociationContract.test_face_match_metadata_block_is_exact` | P-metadata-dict-keys (8), P-assoc-type-label (3), assoc-field-null P18, metadata-payload-structure P54, identity-arg-none on P (3) | P57-64; P31,40,41; P18; P54; P3,21,45 |
| `TestPropagateAssociationContract.test_update_trust_false_leaves_trust_untouched` | P-or-guard (1), metadata-init-guard P53 | P42; P53 |
| `TestPropagateAssociationContract.test_null_confidence_falls_back_to_zero` | confidence-fallback (3) | P39; L28,29 |

Residual after these 8 tests: **P37** (EQUIVALENT, dataclass default) and the 24 log-text EQUIVALENTs — 25 mutants, all intentionally left alive.

## Two structural notes for WP4.4

1. **These mocks cannot see SQL.** The cheapest systemic fix is a shared helper like `_sql`/`_params` above in `backend/tests/unit/services/` (or `conftest.py`) so every service test with a mocked `AsyncMock` session can assert on the statement it built. This module's 12 SQL-construction survivors are the visible symptom; the same blind spot exists wherever `session = AsyncMock()` is the fixture.
2. **No production callers.** Nothing outside the test file imports these three methods. WP4.4 tests are the only guard these methods will ever have, so response-shape `set(entry) == {...}` assertions (rather than `in`) are the right strength, not over-specification.
