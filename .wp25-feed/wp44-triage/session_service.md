# WP4.4 Triage Dossier — backend/services/session_service.py

Wave: mutation-testing survivor triage (WP4.3 feed → WP4.4)
Status: **UNVERIFIED** — no tests were run (live mutation run owns the machine; read-only triage per harness constraints).

## Provenance

- Verdicts: `mutants/backend/services/session_service.py.meta` — 60 keys, 25 killed, **35 survived**, 0 unchecked.
- Diffs: `uv run mutmut show <key>` (all 35 succeeded; no manual-diff fallback needed).
- Coverage: `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`. ALL covering tests for every
  survivor function are in **`backend/tests/unit/test_session_service.py`** (create: 12 tests, get: 9,
  ttl: 2, refresh: 1). Fixture `mock_redis_client` is a blanket `AsyncMock` (backend/tests/conftest.py:2166)
  — every redis method accepts ANY args, so arg-mutation mutants can only die via explicit
  `assert_called_*_with(...)` style assertions.
- Source under mutation: `backend/services/session_service.py` (191 lines, small module).

## Root cause of the survivor population

The existing test suite asserts Redis interactions almost exclusively via
`assert_called_once()` / `session_id in str(call_args[0][0])` (substring on first positional arg).
It never pins **the key**, **the serialized payload contents**, or **the `expire` value** — so every
"replace argument with None / rename string key / drop argument" mutant walks through untouched.
`test_session_ttl_set_correctly` (test file line 243-254) is the emblem: its whole assertion is
`assert call_args is not None`.

## Consumer reality (classification evidence)

- `backend/api/middleware/auth.py:383-386`: validates sessions via `get_session(...)` then
  `session_data.get("user_id") is not None` — the stored blob's **`user_id` key name is load-bearing**.
- `backend/api/routes/auth.py:312-318` creates sessions with `ttl=timedelta(hours=24)`;
  auth.py:435 reads back `user_id` from the blob. Expired sessions become 401s; the SessionExpiredError
  **message text** is not surfaced to clients (auth.py:437-441 uses fixed detail "Session expired").

## Cluster table (counts sum to 35)

| # | Cluster | Mutants | Count | Class | Kill via |
|---|---------|---------|-------|-------|----------|
| C1 | `create_session` ValueError **message text** only (`msg="user_id cannot be None"` → None / XX-wrapped / lower / upper; `ValueError(msg)` → `ValueError(None)`) | create_session__mutmut_2, _3, _4, _5, _6 | 5 | EQUIVALENT | — (exception type + control flow identical; no consumer reads args) |
| C2 | `create_session` `secrets.token_urlsafe(32)` → `token_urlsafe(None)` | create_session__mutmut_8 | 1 | EQUIVALENT | — (`nbytes=None` IS the stdlib default = 32 bytes; byte-identical distribution) |
| C3 | `create_session` token entropy tweak `token_urlsafe(32)` → `token_urlsafe(33)` (44-char token vs 43) | create_session__mutmut_9 | 1 | LOW-VALUE | — (real +1 byte entropy; only asserted property `len>10` still holds; exact-length assertions would be brittle) |
| C4 | `create_session` **stored payload content never asserted**: `full_data=None`; `"user_id"` → `"XXuser_idXX"`/`"USER_ID"`; `"session_id"` → `"XXsession_idXX"`/`"SESSION_ID"`; set-value → `None`; set-value arg dropped; `json.dumps(full_data)` → `json.dumps(None)` | create_session__mutmut_10, _11, _12, _13, _14, _21, _24, _26 | 8 | **TEST-GAP** | T1 |
| C5 | `create_session` **TTL/expire value never asserted**: `ttl_seconds=None`; `expire=ttl_seconds` → `expire=None`; expire kwarg deleted | create_session__mutmut_15, _22, _25 | 3 | **TEST-GAP** | T2 (+T3 custom-TTL leg) |
| C6 | `create_session` `redis.set` positional shift — key arg deleted, payload lands in `args[0]` | create_session__mutmut_23 | 1 | **TEST-GAP** | T1/T4 (existing substring check `session_id in str(args[0])` accidentally passes because the payload itself contains session_id) |
| C7 | `get_session` ValueError **message text** only (`msg="session_id cannot be empty"` → None / XX-wrapped / upper; `ValueError(msg)` → `ValueError(None)`) | get_session__mutmut_2, _3, _4, _5 | 4 | EQUIVALENT | — (`pytest.raises(ValueError)` type preserved) |
| C8 | `get_session` `SessionExpiredError(f"Session {id} ...")` → `SessionExpiredError(None)` (message arg lost; raise preserved) | get_session__mutmut_11 | 1 | LOW-VALUE | — (consumers map to fixed 401 "Session expired" / boolean; str(exc) unused) |
| C9 | `get_session` falsy-guard widening `dict(data) if data else {}` → `if (data) or True else {}` | get_session__mutmut_13 | 1 | EQUIVALENT | — (None is handled upstream; falsy non-str/bytes Redis values ({}, [], ()) map to {} both ways; only truly-impossible values (0, set()) diverge) |
| C10 | `get_session_ttl` **key identity never asserted**: `key=None`; `_session_key(None)` ("session:None"); `ttl(None)` | get_session_ttl__mutmut_1, _2, _4 | 3 | **TEST-GAP** | T5 (existing test only `assert_called_once()`, line 277) |
| C11 | `refresh_session` **expire() key/seconds args never asserted**: `key=None`; `_session_key(None)`; `ttl_seconds=None`; `expire(None, n)`; `expire(key, None)`; `expire(ttl_seconds)` (key arg dropped); `expire(key,)` (timeout arg dropped) | refresh_session__mutmut_1, _2, _3, _6, _7, _8, _9 | 7 | **TEST-GAP** | T6 (sole covering test asserts `assert_called_once()` only, line 299) |

**Totals: 35 = EQUIVALENT 11 (C1,C2,C7,C9) + LOW-VALUE 2 (C3,C8) + TEST-GAP 22 (C4,C5,C6,C10,C11).**

## Why the TEST-GAP clusters matter (not LOW-VALUE)

- C4: the auth middleware's session validity check (`middleware/auth.py:386`) literally reads
  `session_data.get("user_id")` from the blob `create_session` writes. Renaming the stored key
  breaks session validation on login — a security-relevant behavior change the unit tests execute
  past but never look at (the suite always mocks `redis.get` with a canned dict, so the
  create→store→read round trip is never exercised against what was actually written).
- C5: `expire=None` / expire-deleted means the session key is written with **no TTL** — sessions
  never expire (retention design says 30 days; auth route asks for 24h TTL). Real durability bug class.
- C10/C11: wrong key means TTL inspection refresh hit a nonexistent `session:None` / `None` key —
  silent no-ops in production against real Redis.

## Drafted tests (UNVERIFIED — not yet run red/green)

All five belong in **`backend/tests/unit/test_session_service.py`** (the sole covering test file).
Style follows the existing file: `@pytest.mark.asyncio`, `mock_redis_client: MagicMock` fixture,
class-scoped methods. T1/T2/T4 append to `TestSessionCreation`; T5/T6 append to `TestSessionTTL`.
TDD procedure per test: apply the cluster's mutant to `backend/services/session_service.py`, run the
new test → must FAIL (red); revert to original → must PASS (green).

### T1 — kills C4 (8 mutants) and also C6/_23, C5/_15 indirectly

Insert into `class TestSessionCreation:` (after `test_create_session_empty_data`, line ~101):

```python
    @pytest.mark.asyncio
    async def test_create_session_stores_serialized_payload_with_identity_metadata(
        self, mock_redis_client: MagicMock
    ) -> None:
        """Stored JSON payload must carry caller data plus user_id/session_id identity keys.

        The auth middleware validates sessions by reading user_id from the stored
        blob (api/middleware/auth.py), so the exact key names and JSON serialization
        are load-bearing contract, not implementation detail.
        """
        mock_redis_client.set = AsyncMock(return_value=True)
        service = SessionService(mock_redis_client)
        session_data = {"email": "test@example.com", "role": "admin"}

        session_id = await service.create_session("user_42", session_data)

        call = mock_redis_client.set.call_args
        raw_payload = call.args[1]
        assert isinstance(raw_payload, str), "session payload must be a JSON string"
        stored = json.loads(raw_payload)
        assert stored == {
            "email": "test@example.com",
            "role": "admin",
            "user_id": "user_42",
            "session_id": session_id,
        }
```

Add to the module import block at top of file (line 13-18 region): `import json` (stdlib import
before `from datetime import timedelta`, matching isort ordering).
Kills: _10/_21/_24/_26 (payload destroyed/mis-serialized → json.loads raises or mismatches),
_11/_12/_13/_14 (renamed identity keys break the dict equality), _23 (payload shifts to args[1]
missing → IndexError on `call.args[1]`).

### T2 — kills C5 default-TTL leg (3 mutants)

Insert into `class TestSessionCreation:`:

```python
    @pytest.mark.asyncio
    async def test_create_session_sets_default_24h_expire_on_redis_set(
        self, mock_redis_client: MagicMock
    ) -> None:
        """Default session must be written with expire=86400 seconds (24h TTL).

        Mutation survivors replace ttl_seconds/expire with None or delete the
        kwarg — that writes session keys with no expiry at all.
        """
        mock_redis_client.set = AsyncMock(return_value=True)
        service = SessionService(mock_redis_client)

        await service.create_session("user123", {"device": "desktop"})

        mock_redis_client.set.assert_called_once()
        call = mock_redis_client.set.call_args
        assert call.kwargs["expire"] == 86400
```

Kills: _15 (expire=None), _22 (expire=None), _25 (KeyError — kwarg deleted).

### T3 — custom TTL leg (same cluster C5; guards the `ttl or default` branch)

Insert into `class TestSessionCreation:` (complements existing weak `test_create_session_with_custom_ttl`):

```python
    @pytest.mark.asyncio
    async def test_create_session_custom_ttl_passed_as_expire_seconds(
        self, mock_redis_client: MagicMock
    ) -> None:
        """Custom timedelta TTL must reach Redis as exact integer seconds."""
        mock_redis_client.set = AsyncMock(return_value=True)
        service = SessionService(mock_redis_client)

        await service.create_session("user123", {"device": "mobile"}, ttl=timedelta(hours=2))

        call = mock_redis_client.set.call_args
        assert call.kwargs["expire"] == 7200
```

### T4 — kills C6/_23 head-on (arg-shape contract)

Insert into `class TestSessionCreation:`:

```python
    @pytest.mark.asyncio
    async def test_create_session_redis_set_receives_prefixed_key_as_first_positional_arg(
        self, mock_redis_client: MagicMock
    ) -> None:
        """redis.set call shape must be (session:<id>, payload, expire=...).

        The existing substring check `session_id in str(args[0])` is satisfied by the
        payload blob too, so an arg-deletion mutant passes today. Pin the full shape.
        """
        mock_redis_client.set = AsyncMock(return_value=True)
        service = SessionService(mock_redis_client)

        session_id = await service.create_session("user123", {"device": "desktop"})

        call = mock_redis_client.set.call_args
        assert len(call.args) == 2
        assert call.args[0] == f"session:{session_id}"
```

### T5 — kills C10 (3 mutants)

Insert into `class TestSessionTTL:` (after `test_get_session_ttl_expired`, line ~287):

```python
    @pytest.mark.asyncio
    async def test_get_session_ttl_queries_prefixed_key(
        self, mock_redis_client: MagicMock
    ) -> None:
        """get_session_ttl must query the exact session:<id> key, not None/None-keyed variant.

        Existing test only asserts ttl was called once; key mutations (None key,
        'session:None') silently return -2 for live sessions against real Redis.
        """
        mock_redis_client.ttl = AsyncMock(return_value=3600)
        service = SessionService(mock_redis_client)

        ttl = await service.get_session_ttl("session_123")

        assert ttl == 3600
        mock_redis_client.ttl.assert_called_once_with("session:session_123")
```

### T6 — kills C11 (7 mutants)

Insert into `class TestSessionTTL:` (replaces nothing; strengthens `test_refresh_session_ttl`):

```python
    @pytest.mark.asyncio
    async def test_refresh_session_calls_expire_with_key_and_seconds(
        self, mock_redis_client: MagicMock
    ) -> None:
        """refresh_session must call expire(session:<id>, int(new_ttl_seconds)).

        Sole covering test asserts only assert_called_once(); every key/seconds
        argument mutation (None key, None seconds, dropped positional args) survives.
        """
        mock_redis_client.expire = AsyncMock(return_value=True)
        service = SessionService(mock_redis_client)

        result = await service.refresh_session("session_123", timedelta(hours=2))

        assert result is True
        mock_redis_client.expire.assert_called_once_with("session:session_123", 7200)
```

## Coverage after drafted tests (predicted, UNVERIFIED)

T1..T6 kill all 22 TEST-GAP survivors (C4 8 + C5 3 + C6 1 + C10 3 + C11 7 = 22; T1 and T2/T4 overlap
on _15/_23, still fully covered). Remaining 13 (C1, C2, C3, C7, C8, C9) stand as EQUIVALENT/LOW-VALUE
noise — candidate mutmut exemptions if the ratchet needs them.

## Covering test file references

- `backend/tests/unit/test_session_service.py` — sole covering file for all survivors:
  - `TestSessionCreation` lines 35-101 (weak: no payload assertion; :53-66 key check is substring-only)
  - `TestSessionRetrieval` lines 109-173
  - `TestSessionTTL` lines 239-299 (weak: :252-254 `assert call_args is not None`; :277/:299 `assert_called_once()` with no args)
  - `TestSessionEdgeCases` lines 307-369 (ValueError type checks only — C1/C7 survivors)
- Fixture: `backend/tests/conftest.py:2166` (`mock_redis_client`, blanket AsyncMock)
