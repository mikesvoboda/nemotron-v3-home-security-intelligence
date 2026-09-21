# WP4.4 Triage Dossier — `backend/services/evaluation_queue.py`

- **Source**: `backend/services/evaluation_queue.py` (200 lines) — thin Redis ZSET wrapper (`EvaluationQueue`) + module-level singleton (`get_evaluation_queue` / `reset_evaluation_queue`).
- **Covering test file (only one)**: `backend/tests/unit/services/test_evaluation_queue.py` (412 lines; fixture `mock_redis` L28-39 = all-`AsyncMock`; no `caplog` anywhere, no `assert_called_with` on `zrange` for the ops that matter).
- **Verdict state** (`mutants/backend/services/evaluation_queue.py.meta`): 104 keys → **50 survived**, 54 killed, 0 unchecked. Fully checked — no partial-run caveat.
- **Diffs**: all 50 retrieved via `uv run mutmut show <key>` (0 failures). Raw dump: `/tmp/wp25-scratch/eq_diffs.txt`.
- **Cluster totals verified**: 11 clusters, counts sum to exactly 50 (7+2+2+1+1+7+8+11+4+5+2 = 50; per-function: enqueue 15, dequeue 12, get_pending_events 14, remove 6, get_size 1, is_queued 1, get_evaluation_queue 1 = 50).

## Why so many survive (root cause, one sentence)

The suite asserts only the public return value and (sometimes) that the mock redis call happened — it never pins the **arguments to `zrange`** (so the whole limit-clamping arithmetic survives), never asserts the **singleton captured the passed redis client**, and never inspects **log records** — but 33 of the 50 survivors are log-line cosmetics (`extra` dict keys clobbered to `XXevent_idXX`/`EVENT_ID`, `extra=None`, message →`None`) that are write-only with zero production readers.

## Cluster table

Counts sum = 50. "Src" = original file lines. Key lists are complete (small module).

| # | Pattern (function @ src lines) | N | Keys | Class | Killed by |
|---|---|---:|---|---|---|
| C01 | `get_pending_events` zrange arg clobbers (L128): key→`None` (_3), start→`None` (_4), stop→`None` (_5), arg dropped (_6 start / _7 stop / _8 stop-empty), start 0→1 (_9) | 7 | _3, _6, _9 | **TEST-GAP** | Draft 1 |
| C02 | `get_pending_events` stop index off-by-one (L128): `limit - 1` → `limit + 1` (_10) / `limit - 2` (_11) — silently returns one too many / one too few pending events | 2 | _10, _11 | **TEST-GAP** | Draft 2 |
| C03 | `get_pending_events` bytes-decode branch logic (L131): `and False` drops str branch (_14), `or True` drops bytes branch (_15) | 2 | _14, _15 | **TEST-GAP** | Draft 2 (type-mixing fixture) |
| C04 | `get_evaluation_queue` singleton ignores `redis_client` arg (L193): `EvaluationQueue(redis_client)` → `EvaluationQueue(None)` | 1 | _3 | **TEST-GAP** | Draft 3 |
| C05 | `get_pending_events` default `limit=100` → `101` (L118) | 1 | _1 | **TEST-GAP** | Draft 4 |
| C06 | `enqueue` debug-log `extra`/message cosmetics (L62-65): msg→None (_7), extra→None (_8)/dropped (_10), keys `XXevent_idXX` (_11) / `EVENT_ID` (_12) / `XXpriorityXX` (_13) / `PRIORITY` (_14) | 7 | _7, _11, _14 | EQUIVALENT | n/a |
| C07 | `enqueue` error-log cosmetics (L68-71): msg→None (_16), extra→None (_17)/dropped (_19), key clobbers (_20, _21, _22, _23), `str(e)`→`str(None)` (_24) | 8 | _16, _20, _24 | EQUIVALENT | n/a |
| C08 | `dequeue` log cosmetics (L93-96, L100-103): debug msg→None (_13), extra→None (_14)/dropped (_16), key clobbers (_17,_18); error msg→None (_19), extra→None (_20)/dropped (_22), key clobbers (_23,_24), `str(None)` (_25) | 11 | _13, _17, _25 | EQUIVALENT | n/a |
| C09 | `logger.error(msg)` → `logger.error(None)` in `get_size` (_2, L115), `get_pending_events` (_21, L135), `remove` (_15, L158), `is_queued` (_8, L174) | 4 | get_size_2, is_queued_8, remove_15 | EQUIVALENT | n/a |
| C10 | `remove` debug-log cosmetics (L152-155): msg→None (_7), extra→None (_8)/dropped (_10), key clobbers (_11,_12) | 5 | _7, _8, _11 | EQUIVALENT | n/a |
| C11 | codec-name case `utf-8` → `UTF-8` (dequeue _10 L90; get_pending_events _18 L131) | 2 | dq_10, gpe_18 | EQUIVALENT | n/a |

**Totals: TEST-GAP 13, EQUIVALENT 37, LOW-VALUE 0.**

### Classification notes

- **C01-C03, C05 are the real payload.** `get_pending_events` (src L118-136) is the entire surface of the module where nothing about the Redis call is pinned: `test_get_pending_events` (test file L214-220) sets `zrange.return_value = [b"100", b"200", b"300"]` (a canned 3-element list that survives *any* index change), calls with `limit=10` (≠ default, so L118's `101` mutant is also never exercised), and never touches `zrange.call_args`. Contrast `zpopmax` (dequeue L138), `zcard` (L202) and `zrem` (L239) which *do* have `assert_called_once_with(key)` — that's why sibling-method arg mutants mostly died and this function's didn't.
  - _9 (`0→1`) and _11 (`limit-1 → limit-2`) are the dangerous survivors: they silently drop the first (or last) pending event from whatever listing/ops UI consumes this.
  - Decode-branch pair _14/_15 differ: _15 (`or True` → decode *every* member) is a real behavior change — a str member (what `decode_responses=True` returns in prod, `backend/core/redis.py`) hits `str.decode` → AttributeError → silent `[]`; Draft 2's mixed bytes+str fixture kills it. _14 (`and False` → decode *no* members) stays behaviorally invisible on CPython because `int(b"100")` is legal (verified, 3.14.4); no draft kills it without an unparsable-bytes fixture, which is equally broken on the original. C03 is TEST-GAP on _15's account; _14 is noted de-facto equivalent inside a TEST-GAP cluster.
  - _3, _4, _5, _6, _7, _8 (None/dropped zrange args) would raise `TypeError`/`DataError` against real redis-py but sail through the `AsyncMock`, then land in the `except` handler → `[]`; only `zrange.call_args` pins them.
- **C04**: prod callers exist (`backend/main.py:900`, `backend/services/nemotron_analyzer.py:4587` — the latter passes `self._redis`, which is *not* guaranteed to be the same object as `get_redis()`'s singleton). Existing singleton tests (L373-411) check `isinstance` and identity only, so `EvaluationQueue(None)` passes every test while every queue op would throw post-init. The only pin is `queue._redis is mock_redis`.
- **C06-C10 (33 keys, EQUIVALENT)**: every change is confined to the log *record* — message text, `extra` dict keys, `exc` stringification. The covering suite has zero `caplog` usage; the project's structured-logging pipeline writes `extra` out and nothing in `backend/` reads these keys back. Per WP4.4 convention (precedent: `background_evaluator.md` C23, 42 keys, EQUIVALENT) log-cosmetic survivors are semantically inert.
- **C11 (2, EQUIVALENT)**: `codecs.lookup('utf-8') is codecs.lookup('UTF-8')` → True (verified); the codec name is case-insensitive, so the mutation is byte-identical in effect.

## Drafted tests (4 drafts, kill all 13 TEST-GAP keys)

Target file: `backend/tests/unit/services/test_evaluation_queue.py` (append new classes at end; reuse existing module-level `mock_redis` / `evaluation_queue` fixtures at L28-47; style: `@pytest.mark.asyncio` + AsyncMock + `call_args`).

`// UNVERIFIED - not yet run red/green`

**TDD procedure (one line)**: apply the cluster's one-line diff to `backend/services/evaluation_queue.py`, run the named test → the pinned assertion must FAIL (red); restore the original → PASS (green); then re-run the module's `mutmut run` scope and confirm those keys flip `survived → killed`.

### Draft 1 — pin the `zrange` call contract (kills C01: _3,_4,_5,_6,_7,_8,_9)

```python
class TestGetPendingEventsContract:
    """Pin the exact zrange call contract (WP4.4 C01: index args never asserted)."""

    @pytest.mark.asyncio
    async def test_get_pending_events_queries_from_zero_to_limit_minus_one(
        self, evaluation_queue, mock_redis
    ):
        """zrange must receive (QUEUE_KEY, 0, limit - 1) exactly — inclusive end index."""
        mock_redis.zrange.return_value = []

        await evaluation_queue.get_pending_events(limit=5)

        mock_redis.zrange.assert_called_once_with("evaluation:pending", 0, 4)
```

Red on: _3/_4/_5 (None args), _6/_7 (dropped positional), _8 (missing stop), _9 (`1, limit-1`). Green on original (`0, limit - 1` = `0, 4`).

### Draft 2 — off-by-one window + bytes/str decode branch (kills C02: _10,_11; C03: _14,_15)

```python
    @pytest.mark.asyncio
    async def test_get_pending_events_returns_exactly_limit_items_mixed_types(
        self, evaluation_queue, mock_redis
    ):
        """limit=2 must slice to exactly 2 items (0..limit-1) and decode both bytes and str."""

        # Fake Redis that honors inclusive start/stop indices like a real ZRANGE and
        # returns a mix of bytes and str members (decode_responses can vary).
        def fake_zrange(key, start, stop):
            assert key == "evaluation:pending"
            members = [b"1", b"2", "3", b"4", 5]  # bytes + str + already-int
            if stop < start:
                return []
            return members[start : stop + 1]

        mock_redis.zrange.side_effect = fake_zrange

        events = await evaluation_queue.get_pending_events(limit=2)
        assert events == [1, 2]  # _10 (limit+1 -> 3 items), _11 (limit-2 -> 1 item)

        all_events = await evaluation_queue.get_pending_events(limit=5)
        assert all_events == [1, 2, 3, 4, 5]  # str member kills _15 (or True -> str.decode crash)
```

Red/green trace: _10 → mutant calls `fake_zrange(key, 0, 3)` → 3 items → `[1,2,3] != [1,2]` RED; _11 → stop `-1 < start 0` → `[] != [1,2]` RED; _15 (`or True` → every item decoded) → second call hits `str "3".decode` → `AttributeError` → caught → `[] != [1,2,3,4,5]` RED; _14 (`and False` → nothing decoded) → `int(b"1")`/`int(5)`/`int("3")` all legal on CPython (verified 3.14.4) → returns `[1,2,3,4,5]` → stays GREEN. **_14 is de-facto EQUIVALENT on CPython** — the branch removal is only observable if a bytes member isn't int-parsable, and then original and mutant both raise inside the try and return `[]`. No draft kills _14 without banning `int(bytes)` reliance (a ruff rule, not a test); cluster C03 stays TEST-GAP with that one key noted equivalent (precedent: background_evaluator.md C06's mixed-cluster note).

### Draft 3 — singleton must capture the passed client (kills C04: get_evaluation_queue _3)

```python
class TestSingletonWiring:
    """get_evaluation_queue must wire the redis_client it was handed (WP4.4 C04)."""

    def test_get_evaluation_queue_binds_given_redis_client(self, mock_redis):
        from backend.services.evaluation_queue import (
            get_evaluation_queue,
            reset_evaluation_queue,
        )

        reset_evaluation_queue()
        try:
            queue = get_evaluation_queue(mock_redis)
            assert queue._redis is mock_redis  # mutant EvaluationQueue(None) fails here
        finally:
            reset_evaluation_queue()
```

Red on _3 (`_redis is None`); green on original. Mirrors the `reset_evaluation_queue()` bracketing style of `TestSingletonPattern` (L373-411) but adds try/finally so a red run cannot poison the singleton for other tests (cf. memory: SetupGuard-style cache poisoning).

### Draft 4 — default limit contract (kills C05: get_pending_events _1)

```python
    @pytest.mark.asyncio
    async def test_get_pending_events_default_limit_is_100(self, evaluation_queue, mock_redis):
        """Documented default: limit=100 -> inclusive stop index 99."""
        mock_redis.zrange.return_value = []

        await evaluation_queue.get_pending_events()

        mock_redis.zrange.assert_called_once_with("evaluation:pending", 0, 99)
```

Red on _1 (`101` → stop 100); green on original.

## Kill accounting

| Draft | Keys killed |
|---|---:|
| Draft 1 | 7 (C01: _3,_4,_5,_6,_7,_8,_9) |
| Draft 2 | 3 (C02: _10,_11; C03: _15) |
| Draft 3 | 1 (C04: get_evaluation_queue _3) |
| Draft 4 | 1 (C05: get_pending_events _1) |
| **Total** | **12 of 13 TEST-GAP keys; _14 unkillable (de-facto EQUIVALENT on CPython — see C03)** |

## Covering test file reference

- `backend/tests/unit/services/test_evaluation_queue.py` — all 50 survivors' functions are covered only here (per `tests_by_mangled_function_name`; `test_nemotron_analyzer.py` entries hit `enqueue`/`get_evaluation_queue` only incidentally and assert nothing about them).
- Weak-assert sites: L214-220 (`test_get_pending_events` — canned return, no call_args), L112-118 / L158-165 etc. (exception-path tests assert only the sentinel return — the reason C07/C09 log mutants there are unkillable without caplog, which we deliberately do not add).
