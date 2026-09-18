# WP4.4 Triage Dossier — backend/services/cache_service.py

- **Survivors:** 107 (of 352 tracked keys; source: `mutants/backend/services/cache_service.py.meta`)
- **Method:** all 107 diffs pulled via `uv run mutmut show <key>` (read-only, clean run rc=0);
  clusters verified programmatically — counts sum to 107.
- **Covering unit tests (from `mutants/mutmut-stats.json` `tests_by_mangled_function_name`):**
  - `backend/tests/unit/services/test_cache_service.py` (get_or_set ×9, invalidate ×6, exists ×6,
    refresh ×5, invalidate_events ×1, invalidate_cameras ×2, invalidate_system_status ×1)
  - `backend/tests/unit/services/test_cache_swr.py` (get_or_set_swr ×5, _fetch_and_cache_swr ×4, cached_swr ×5)
- **Repo-wide fact used in classifications:** `grep caplog backend/tests/unit/services/test_cache_service.py
  test_cache_swr.py` → **0 hits**. Neither cache test file ever inspects log records; all
  Redis-error tests (`test_invalidate_handles_error` :330, `test_exists_handles_error` :437,
  `test_refresh_handles_error` :493, `test_swr_handles_redis_error_gracefully` test_cache_swr.py:84)
  assert only the return value.

## Cluster table (sums to 107)

| # | Cluster (pattern @ source lines) | N | Keys (≤3 examples) | Class |
|---|---|---|---|---|
| B3 | `refresh()` Redis-error `logger.warning(msg, extra={...})` payload clobbered — message text → `None`, `extra=` dict dropped/`None`, dict keys upper-cased/`XX..XX`-wrapped, `error_type` value case-changed (cache_service.py:694-716) | 22 | refresh#7, refresh#14, refresh#30 | EQUIVALENT |
| B1 | `invalidate()` Redis-error `logger.warning(..., extra=...)` payload clobber (same shape) + debug-log message clobber (cache_service.py:441-463) | 19 | invalidate#9, invalidate#13, invalidate#18 | EQUIVALENT |
| B2 | `exists()` Redis-error `logger.warning(..., extra=...)` payload clobber (same shape) (cache_service.py:662-684) | 18 | exists#6, exists#11, exists#25 | EQUIVALENT |
| F | `_fetch_and_cache_swr()`: `total_ttl = ttl + stale_ttl` → `ttl - stale_ttl`/`None`; `self.set(key, result, ttl=total_ttl)` arg clobbers incl. **kwarg-drop → silent DEFAULT_TTL=300 fallback**; `fresh_until = time.time() + ttl` → `None`/`- ttl`; `self._redis.set(freshness_key, str(fresh_until), expire=total_ttl)` key/value/expire clobbers, `expire=` dropped (**marker never expires**), positional-shift (cache_service.py:368-386) | 17 | _fetch_and_cache_swr#7, #13, #18 | **TEST-GAP** |
| G | `invalidate_events/cameras/system_status()` pass-through to `invalidate_pattern`: `reason=` → `None`/dropped (→ default `MANUAL`), `cache_type=` → `None`/dropped/case-and-`XX..XX`-wrapped label (cache_service.py:545-596) | 14 | invalidate_events#2, invalidate_system_status#9, invalidate_cameras#3 | **TEST-GAP** |
| E | `get_or_set_swr()`: `metric_type = cache_type or self._infer_cache_type(key)` → `None`/`and`; `self.get(key, cache_type=cache_type)` → `cache_type=None`/kwarg-dropped (metric-type plumbing; falsy-cache_type variant **crashes** label processing in prod) (cache_service.py:302, 308) | 4 | get_or_set_swr#4, #5, #11 | **TEST-GAP** |
| D | `get_or_set_swr()` freshness plumbing: `full_key`/`freshness_key` derivation → `None`, `redis.get(freshness_key)` → skipped/`get(None)` (**always stale — SWR silently dead**), `if now < fresh_until:` → `<=` (off-by-one on freshness expiry boundary), `_fetch_and_cache_swr(key,...)` → `None` (cache_service.py:303-322, 344) | 6 | get_or_set_swr#15, #20, #22 | **TEST-GAP** |
| A | `get_or_set`/`get_or_set_swr` debug/error log **message text** clobbered to `None` (cache_service.py:249, 260, 343) | 3 | get_or_set#4, get_or_set#14, get_or_set_swr#21 | EQUIVALENT |
| C | `invalidate()`: `if deleted > 0:` guard around the debug log → `>= 0` / `> 1` (changes only whether a debug line fires; return uses its own expression) (cache_service.py:441) | 2 | invalidate#4, invalidate#5 | EQUIVALENT |
| H | `cached_swr(cache_type="other")` **default** label → `"XXotherXX"`/`"OTHER"` (metrics label only; every repo usage site passes cache_type explicitly) (cache_service.py:986) | 2 | x_cached_swr#1, x_cached_swr#2 | LOW-VALUE |

3 + 19 + 18 + 22 + 2 + 6 + 4 + 17 + 14 + 2 = **107** ✔

## Classification rationale

- **B1/B2/B3 (59 survivors — the "extra= dict" machine-mutants).** These clobber only the `extra=`
  structured-log payload and the message string of the three *graceful-degradation* warning branches.
  Grep of the repo shows **no machine consumer** of the cache log `error_type` field: frontend hits
  for `error_type` are Prometheus *label* consumers of `hsi_pipeline_errors_total` and WebSocket
  payloads — a different transport (metrics/WS), not these log records. Return values (`False`) are
  already asserted. `extra=` keys/values are pure observability text. Verdict: **EQUIVALENT for
  test purposes** — not worth hand-writing 59 per-field caplog asserts. **Feed recommendation:**
  do not draft tests; adopt a kill-through/suppression policy for "log-call argument" mutants in
  WP4.4 (or one cheap caplog smoke test per branch later if a JSON-schema log contract ever lands —
  repo precedent for extra-field asserts exists: `backend/tests/integration/services/test_calibration_impact_workflow.py:622`).
- **A/C (5).** Debug/error message text + a guard around a debug log. Exception is re-raised /
  return value unchanged. **EQUIVALENT.**
- **H (2).** Default-label change of the decorator; changes only a Prometheus label when a caller
  omits `cache_type` (none do today, but future callers might). **LOW-VALUE.**
- **F/D/E/G (41).** Real behavior changes on *covered* lines that existing tests execute but never
  assert:
  - **F**: the only existing assertion is `assert mock_redis_client.set.called`
    (test_cache_swr.py:80, :271) — true for *any* args. The TTL sum (`ttl + stale_ttl`), the
    freshness-marker value/expiry, and kwarg identity are unasserted. `#13` (kwarg drop →
    silent 300s default) and `#18/#21` (expire dropped → marker lives as long as… never) are
    genuine SWR-correctness changes nobody checks.
  - **D**: `#15` (skip freshness-marker read → every hit is "stale", background refresh storm,
    SWR benefit zero) survives precisely because the only "fresh data" test
    (`test_swr_returns_fresh_data_immediately`) lets the stale path run and still passes — the
    background refresh is a fire-and-forget task the factory assert can't see. `#20` flips the
    expiry boundary. `#7/#8/#16` break key derivation so the marker is never found.
  - **E**: metric-type plumbing is never asserted for SWR; worse, the `and`-flipped `#5` (and
    `#4` `None`) produce `record_cache_stale_hit(None)` on the stale path, which raises
    `ValueError: label value None is invalid` inside the **caller's** request path in prod.
  - **G**: `test_invalidate_events_uses_correct_pattern` (test_cache_service.py:1000) asserts only
    `scan_iter(match=...)`; only `invalidate_cameras`' custom-reason path asserts the metric
    (`("cameras","camera_deleted")`, :1052). The *default* reason/cache_type per invalidator
    (e.g. dropping `reason=` → silently reports `"manual"` instead of `"event_created"`) is
    unasserted for events/system_status (and default-reason for cameras).

## Drafted tests (6) — for the highest-value TEST-GAP clusters

// UNVERIFIED - not yet run red/green (per WP4.3 read-only constraint: no pytest executed)

TDD procedure (same for all): apply the mutant source per key → run the named test → assertion
must FAIL (red); restore original → run → PASS (green). Kill claims below are static-analysis
verdicts pending that loop.

### 1. `test_fetch_and_cache_swr_stores_value_and_freshness_marker_with_total_ttl` → kills cluster F (17 keys: `_fetch_and_cache_swr#4-10,13-22`)

Target: `backend/tests/unit/services/test_cache_swr.py`. New imports at top of file:
`import asyncio` (not needed here), `from freezegun import freeze_time`,
and add `CACHE_PREFIX` to the `from backend.services.cache_service import (...)` block.

```python
@pytest.mark.asyncio
async def test_fetch_and_cache_swr_stores_value_and_freshness_marker_with_total_ttl(
    cache_service, mock_redis_client
):
    """SWR fetch stores the value under the prefixed key with (ttl + stale_ttl) expiry
    and writes a fresh_until marker = now + ttl expiring at the same total TTL."""
    with freeze_time("2026-01-15 10:00:00"):
        now = time.time()
        result = await cache_service._fetch_and_cache_swr(
            "stats:dashboard", lambda: {"value": 1}, ttl=60, stale_ttl=30
        )

    assert result == {"value": 1}
    # Value stored under the real prefixed key with the SUMMED ttl (not default 300)
    mock_redis_client.set.assert_any_await(
        f"{CACHE_PREFIX}stats:dashboard", {"value": 1}, expire=90
    )
    # Freshness marker: now + ttl, stringified, expiring with total_ttl (never no-expiry)
    mock_redis_client.set.assert_any_await(
        f"{CACHE_PREFIX}stats:dashboard:fresh_until", str(now + 60), expire=90
    )
```

Red/green: on `_fetch_and_cache_swr#7` (`ttl - stale_ttl` → `expire=30`), `#13` (kwarg dropped →
`expire=300`), `#18/#21` (`expire=None`/absent → marker never expires), `#14/#15/#22` (marker
value `"None"`/past), `#16/#17/#19/#20` (key/value clobbered or positional shift), `#4-#6/#8-#10`
(key/total_ttl clobbered) the `assert_any_await` calls fail; pass on original. Deterministic under
`freeze_time` (both sides compute the same frozen epoch + 60).

### 2. `test_get_or_set_swr_stale_hit_metric_uses_resolved_cache_type` → kills E#4, E#5

Target: `backend/tests/unit/services/test_cache_swr.py`.

```python
@pytest.mark.asyncio
async def test_get_or_set_swr_stale_hit_metric_uses_resolved_cache_type(
    cache_service, mock_redis_client
):
    """On the stale path the metric label must be the resolved metric type
    (explicit cache_type, else inferred from the key) - never None."""
    from backend.core.metrics import record_cache_stale_hit  # noqa: F401 (patched below)

    cached = {"status": "ok"}
    stale_marker = str(time.time() - 10)  # fresh_until already passed

    def fake_get(key):
        if key == "cache:system:status":
            return cached
        if key == "cache:system:status:fresh_until":
            return stale_marker
        return None

    mock_redis_client.get.side_effect = fake_get
    factory = MagicMock(return_value={"fresh": True})

    with (
        patch(
            "backend.core.metrics.record_cache_stale_hit", autospec=True
        ) as mock_stale,  # function-local import -> patch at origin
        patch("backend.services.cache_service.asyncio.create_task") as mock_task,
    ):
        result = await cache_service.get_or_set_swr("system:status", factory, ttl=60, stale_ttl=30)

    assert result == cached
    mock_stale.assert_called_once_with("system")  # inferred via _infer_cache_type
    mock_task.assert_called_once()
```

Red/green: on `#4` (`metric_type = None`) and `#5` (`cache_type and ...` → `None` for the falsy
default) `mock_stale` receives `None` → assert fails; passes on original (`"system"`).

### 3. `test_get_or_set_swr_forwards_explicit_cache_type_to_get_metrics` → kills E#11, E#13 (+ D#22)

Target: `backend/tests/unit/services/test_cache_swr.py`.

```python
@pytest.mark.asyncio
async def test_get_or_set_swr_forwards_explicit_cache_type_to_get_metrics(
    cache_service, mock_redis_client
):
    """An explicit cache_type must reach self.get()'s hit/miss metric even when the key
    would infer a different type; misses must store under the prefixed key."""
    mock_redis_client.get.return_value = None  # cache miss
    factory = MagicMock(return_value={"computed": True})

    with patch("backend.services.cache_service.record_cache_miss", autospec=True) as mock_miss:
        result = await cache_service.get_or_set_swr(
            "cameras:list", factory, ttl=60, stale_ttl=30, cache_type="system"
        )

    assert result == {"computed": True}
    # Explicit "system" wins over the "cameras" the key would infer
    mock_miss.assert_called_once_with("system")
    # Miss path stored the value under the real prefixed key (not "cache:None")
    mock_redis_client.set.assert_any_await("cache:cameras:list", {"computed": True}, expire=90)
```

Red/green: on `#11`/`#13` (cache_type not forwarded) the label is `"cameras"` → fails; on `#22`
(`_fetch_and_cache_swr(None, ...)` → `set("cache:None", ...)`) the `assert_any_await` fails; pass
on original.

### 4. `test_swr_future_freshness_marker_is_fresh_and_skips_refresh` → kills D#7, D#8, D#15, D#16

Target: `backend/tests/unit/services/test_cache_swr.py`. This is the guard that
`test_swr_returns_fresh_data_immediately` misses (it can't see the stale branch because the
refresh runs in a detached task).

```python
@pytest.mark.asyncio
async def test_swr_future_freshness_marker_is_fresh_and_skips_refresh(
    cache_service, mock_redis_client
):
    """A marker in the future means fresh: no stale metric, no background refresh task.
    Guards the freshness-key read/derivation (mutants that skip it make every hit stale)."""
    cached = {"stats": "data"}
    fresh_marker = str(time.time() + 100)

    def fake_get(key):
        if key == "cache:stats:dashboard":
            return cached
        if key == "cache:stats:dashboard:fresh_until":
            return fresh_marker
        return None  # any derived/clobbered key shape lands here

    mock_redis_client.get.side_effect = fake_get
    factory = MagicMock(return_value={"refreshed": True})

    with (
        patch("backend.core.metrics.record_cache_stale_hit", autospec=True) as mock_stale,
        patch("backend.services.cache_service.asyncio.create_task") as mock_task,
    ):
        result = await cache_service.get_or_set_swr(
            "stats:dashboard", factory, ttl=60, stale_ttl=30, cache_type="system"
        )

    assert result == cached
    factory.assert_not_called()
    mock_stale.assert_not_called()
    mock_task.assert_not_called()
```

Red/green: `#15` (marker read skipped) and `#16` (`get(None)`) land on the stale path →
`mock_stale` called → fails; `#7/#8` (`full_key`/`freshness_key` → None) make `fake_get` return
`None` for the marker → stale path → fails; pass on original.

### 5. `test_swr_freshness_marker_equal_to_now_is_stale` → kills D#20 (`now <= fresh_until`)

Target: `backend/tests/unit/services/test_cache_swr.py`.

```python
@pytest.mark.asyncio
async def test_swr_freshness_marker_equal_to_now_is_stale(cache_service, mock_redis_client):
    """The freshness boundary is exclusive: fresh_until == now is STALE (strict <)."""
    with freeze_time("2026-01-15 10:00:00"):
        boundary = str(time.time())  # exactly the value the service will compare against

    cached = {"stats": "data"}

    def fake_get(key):
        if key == "cache:stats:dashboard":
            return cached
        if key == "cache:stats:dashboard:fresh_until":
            return boundary
        return None

    mock_redis_client.get.side_effect = fake_get
    factory = MagicMock(return_value={"refreshed": True})

    with (
        patch("backend.core.metrics.record_cache_stale_hit", autospec=True) as mock_stale,
        patch("backend.services.cache_service.asyncio.create_task") as mock_task,
    ):
        result = await cache_service.get_or_set_swr(
            "stats:dashboard", factory, ttl=60, stale_ttl=30, cache_type="system"
        )

    assert result == cached
    mock_stale.assert_called_once_with("system")
    mock_task.assert_called_once()
```

Red/green: on `#20` (`<=`) the value is treated fresh → `mock_stale` not called → fails; passes
on original. (Clock-freeze caveat: per-test `freeze_time` only, per repo fake-clock hygiene rule.)

### 6. `test_specialized_invalidators_report_type_and_default_reason` → kills 12 of G's 14
(events#2, #5, #6, #9, #10; system_status#2, #5, #6, #9, #10; cameras#6; cameras#3/system#3/
events#3 cache_type-None variants are *inference-equivalents* that stay alive by design)

Target: `backend/tests/unit/services/test_cache_service.py` (imports already present:
`CacheInvalidationReason`, `patch`, `AsyncMock`, `MagicMock`, `pytest`).

```python
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "expected_type", "expected_reason"),
    [
        ("invalidate_events", "events", CacheInvalidationReason.EVENT_CREATED),
        ("invalidate_cameras", "cameras", CacheInvalidationReason.CAMERA_UPDATED),
        ("invalidate_system_status", "system", CacheInvalidationReason.STATUS_CHANGED),
    ],
)
async def test_specialized_invalidators_report_type_and_default_reason(
    cache_service, mock_redis_client, method_name, expected_type, expected_reason
):
    """Each specialized invalidator must report (cache_type, default reason) to the
    invalidation metric - dropping reason= silently reports "manual" instead."""
    mock_scan_iter = AsyncMock()
    mock_scan_iter.__aiter__ = lambda self: self
    mock_scan_iter.__anext__ = AsyncMock(
        side_effect=[f"cache:{expected_type}:k1", StopAsyncIteration]
    )

    mock_client = MagicMock()
    mock_client.scan_iter.return_value = mock_scan_iter
    mock_redis_client._ensure_connected.return_value = mock_client
    mock_redis_client.delete.return_value = 1

    with patch(
        "backend.services.cache_service.record_cache_invalidation", autospec=True
    ) as mock_invalidation:
        await getattr(cache_service, method_name)()

    mock_invalidation.assert_called_once_with(expected_type, str(expected_reason))
```

Red/green: `reason=None` (→ `"None"`), `reason=` dropped (→ `"manual"`), and the `"XX..XX"` /
UPPER label mutants fail the exact-call assert; pass on original.

## Feed notes for WP4.4

- **59 of the 107 survivors (B1/B2/B3) are one mutation archetype** — `logger.warning(...,
  extra={dict})` argument clobbering in graceful-degradation branches. Recommend a class-level
  ruling (suppress or caplog-smoke) rather than per-key work; otherwise per-module scores stay
  dominated by observability-text noise.
- The remaining actionable TEST-GAP work is exactly the 6 drafted tests above (41 survivors:
  F17 + G14 + E4 + D6; drafts kill ~39, with 2 cache_type-inference-equivalents in G left by design).
- Existing-test weaknesses found while triaging (worth a comment in the tests, not new tests):
  `assert mock_redis_client.set.called` (test_cache_swr.py:80, :271) — true for any args, the
  single reason most of F survives; `test_swr_returns_fresh_data_immediately` cannot see the
  stale branch because the refresh runs as a detached task.
