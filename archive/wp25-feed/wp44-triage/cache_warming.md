# WP4.4 Triage Dossier — backend/services/cache_warming.py

**Source:** `mutants/backend/services/cache_warming.py.meta` — 212 keys: 108 killed, **100 survived**, 4 still null (excluded).
**Covering test file (sole):** `backend/tests/unit/services/test_cache_warming.py` (all 11 mapped functions resolve to it; anchors below).
**Verdict extraction:** `mutants/backend/services/cache_warming.py.meta` → `exit_code_by_key`, exit_code==0. Diffs via `uv run mutmut show <key>` (all 100 fetched, zero fallback).

## Why so many survive — one structural reason

Every test in `test_cache_warming.py` asserts **counts and order only** (`successful_count`, `failed_count`, `total_items_cached`, `call_order`) plus two weak `cache.set` checks (`assert_called_once()` at :371, key+2-of-4-payload-fields at :395-400). **Nothing asserts:** `duration_ms` / `total_duration_ms` values, `report.strategy`, `WarmingResult.cache_name`, `success is False` (falsy passes `assert not r.success`), the cameras cache key/payload/ttl, the DB statement passed to `session.execute`, or that the singleton propagates `cache_warming_strategy` / `cache_warming_timeout`. Log message/extra payloads are never captured (no caplog).

## Test-file anchors (backend/tests/unit/services/test_cache_warming.py)

| Test | Line |
| --- | --- |
| test_warm_all_disabled | :148 |
| test_warm_parallel_success | :162 |
| test_warm_sequential_success | :188 |
| test_warm_handles_failure | :217 |
| test_warm_timeout | :241 |
| test_singleton_creation / reset | :265 / :279 |
| test_warm_caches_on_startup | :298 |
| test_register_default_warmers | :316 |
| test_warm_cameras_returns_count | :331 |
| test_warm_system_status | :373 |

## Cluster table (14 clusters, counts sum to 100)

Key shorthand: `wa`=CacheWarmer.warm_all, `wp`=CacheWarmer._warm_parallel, `ws`=CacheWarmer._warm_sequential, `wc`=CacheWarmer._warm_cameras, `wss`=CacheWarmer._warm_system_status, `rdw`=CacheWarmer._register_default_warmers, `gcw`=get_cache_warmer. Full key = `backend.services.cache_warming.x[ǁCacheWarmerǁ]<fn>__mutmut_<n>`.

| # | Pattern | n | Class | Example keys | Kills |
|---|---|---|---|---|---|
| 1 | Log **message text** mutated (`logger.info/debug/warning` msg → `None`, `"XX…XX"`, lower/UPPER case): wa 3,4,5,6,15,40; wp 37; wc 24; wss 23,24,25,26 | 12 | EQUIVALENT | wa__3, wp__37, wss__24 | nobody captures logger msg text; pure display strings |
| 2 | Log `extra=` structured payload mutated (dict key rename/case, `extra=None`, `extra=` kwarg deleted): wa 16,18,19,20,21,22,41,43,44,45,46,47,48,49,50,51,52,53 | 18 | LOW-VALUE | wa__16, wa__44, wa__53 | structured fields feed log pipelines, not return values; no caplog-based contract in this suite |
| 3 | wa__12: `results=[]` kwarg removed from disabled-branch `WarmingReport` — `field(default_factory=list)` re-supplies `[]` | 1 | EQUIVALENT | wa__12 | structurally identical output |
| 4 | **Duration arithmetic / None assignments never asserted**: `(perf_counter()-start)*1000` → `/1000`, `+start`, `*1001`, or `duration=None`; and `duration_ms=`/`total_duration_ms=` → `None`. wa 30,31,32,35; wp 7,8,9,10,13,20,21,22,23,26,33,34,35,36,40; ws 8,9,10,11,15 | 24 | TEST-GAP | wa__30, wp__8, ws__9 | test asserts `total_duration_ms == 0` only on the disabled path (:159); durations otherwise unobserved → **D1** |
| 5 | **WarmingResult identity fields clobbered**: `cache_name=name`→`None` at result construction (wp 11,24,38; call-site `run_warmer(None, fn)` wp__49; ws__13) and `items_cached=items` dropped (ws__20, defaults to 0) | 6 | TEST-GAP | wp__11, wp__49, ws__20 | tests index results by position or filter on `success`, never check `cache_name`; sequential test skips `total_items_cached` (:213) → **D4** |
| 6 | `success=False` → `success=None` in timeout/exception results (wp 25,39) — falsy, so report tallies unchanged | 2 | TEST-GAP | wp__25, wp__39 | existing `assert not failed_result.success` (:258) passes on None; needs `is False` → **D4** |
| 7 | `strategy=self._strategy` → `None` in both returned reports (wa 7,34) | 2 | TEST-GAP | wa__7, wa__34 | no test reads `report.strategy` → **D1** |
| 8 | wa__24: `results: list[WarmingResult] = []` → `None` — if `warm_all` catches an internal error, report build/`successful_count` raises TypeError instead of returning a graceful empty report (violates the documented fail-soft contract) | 1 | TEST-GAP | wa__24 | no test forces the outer except-branch → **D1** |
| 9 | ws__5: sequential `asyncio.wait_for(fn(), timeout=self._timeout)` → `timeout=None` — sequential path loses all timeout enforcement | 1 | TEST-GAP | ws__5 | timeout test is PARALLEL-only (:241-259); a hung sequential warmer would wedge startup → **D6** |
| 10 | **_warm_cameras cache.set contract unasserted**: cache key `None`/rename/dropped (16,19,22,23), payload `None`/dropped (17,20), payload dict keys `id/name/folder_path/status` renamed XX/UPPER (7,8,9,10,11,12,13,14,15), `ttl=None`/dropped (18,21) | 17 | TEST-GAP | wc__16, wc__8, wc__18 | test asserts only `count == 1` and `set.assert_called_once()` (:370-371) → **D2** |
| 11 | wc 4,5: DB query clobbered — `session.execute(None)`, `select(None)` — statement never inspected | 2 | TEST-GAP | wc__4, wc__5 | `AsyncMock` accepts any statement → **D2** |
| 12 | **_warm_system_status payload/ttl unasserted**: dict keys `environment`, `warmed_at` renamed XX/UPPER (8,9,10,11), `ttl=None`/`ttl=` dropped (17,20) | 6 | TEST-GAP | wss__8, wss__10, wss__17 | existing test checks key + `app_name` + `app_version` only (:397-400) → **D5** |
| 13 | rdw 2,8,14: default warmer registered as `register_warmer("cameras", None)` etc. — warming that cache would crash | 3 | TEST-GAP | rdw__2, rdw__14 | test asserts names present only (:326-329), not the callables → **bonus edit B1** |
| 14 | **get_cache_warmer singleton ignores settings**: `strategy` local → None (3), `strategy=` → None / kwarg removed (6,8), `timeout_seconds=` → None / removed (7,9) | 5 | TEST-GAP | gcw__3, gcw__7, gcw__9 | singleton tests assert identity only (:276,:291); invisible under mock settings (`"parallel"`, `30.0`) because those equal the defaults — diverge on any non-default config → **D3** |

Totals (folded from the table, key-set verified against the meta: 100 assigned, 0 overlap, 0 missing): EQUIVALENT 13 (clusters 1,3), LOW-VALUE 18 (cluster 2), TEST-GAP 69 (clusters 4-14). 12+18+1+24+6+2+2+1+1+17+2+6+3+5 = **100**.

Highest-value gaps: cluster 4 (24 mutants, duration metric is the report's headline number), 10+11 (19 mutants — `_warm_cameras` effectively has no cache-write contract), 14 (config plumbing entirely untested), 9 (safety behavior missing on one of two strategies), 5+6+7+8 (report/result contract).

## Drafted tests  // UNVERIFIED — not yet run red/green

All additions go in `backend/tests/unit/services/test_cache_warming.py`, reusing the existing `mock_settings` fixture (:19) and AsyncMock/patch style. TDD procedure for each: run against the mutant copy → the named assertion fails (or the call errors), run against original → passes.

### D1 — TestWarmingMetricContract (kills cluster 4, plus 7 and 8)

Clock is patched to tick 0.05s per call; with one warmer the call order is deterministic: warm_all start=100.00, warmer start=100.05, warmer end=100.10, warm_all end=100.15 → warmer duration 50.0ms, total 150.0ms. (`asyncio.sleep` uses loop monotonic time, not `perf_counter`, so the tick budget is only consumed by the four instrumented calls — verify no logging middleware calls `perf_counter` if the exact values wobble.)

```python
class TestWarmingMetricContract:
    """Durations and strategy reported by warm_all must be real values (WP4.4)."""

    @staticmethod
    def _fake_clock():
        state = {"n": 0}

        def tick():
            value = 100.0 + state["n"] * 0.05
            state["n"] += 1
            return value

        return tick

    @pytest.mark.asyncio
    async def test_warm_all_reports_accurate_durations_and_strategy(self, mock_settings):
        async def fake_warmer():
            return 5

        with (
            patch(
                "backend.services.cache_warming.get_settings",
                return_value=mock_settings,
                autospec=True,
            ),
            patch("time.perf_counter", side_effect=self._fake_clock()),
        ):
            warmer = CacheWarmer(strategy=WarmingStrategy.PARALLEL)
            warmer.register_warmer("cache1", fake_warmer)
            report = await warmer.warm_all()

        # kills wa__34 (strategy=None); also exercised on disabled path below
        assert report.strategy is WarmingStrategy.PARALLEL
        # kills wa__30 (/1000), wa__31 (+start → 200150.0), wa__32 (*1001 → 150.15), wa__35 (None)
        assert report.total_duration_ms == pytest.approx(150.0)
        result = report.results[0]
        # kills wp__7/_8/_9/_10/_13 (success-branch duration None, /1000, +start, *1001, duration_ms=None)
        assert result.duration_ms == pytest.approx(50.0)
        assert result.items_cached == 5

    @pytest.mark.asyncio
    async def test_sequential_reports_accurate_durations(self, mock_settings):
        async def warm_a():
            await asyncio.sleep(0.01)
            return 5

        async def warm_b():
            await asyncio.sleep(0.01)
            return 10

        with (
            patch(
                "backend.services.cache_warming.get_settings",
                return_value=mock_settings,
                autospec=True,
            ),
            patch("time.perf_counter", side_effect=self._fake_clock()),
        ):
            warmer = CacheWarmer(strategy=WarmingStrategy.SEQUENTIAL)
            warmer.register_warmer("cache1", warm_a)
            warmer.register_warmer("cache2", warm_b)
            report = await warmer.warm_all()

        # kills ws__8/_9/_10/_11/_15 (every seq duration tweak)
        assert [r.duration_ms for r in report.results] == [
            pytest.approx(50.0),
            pytest.approx(50.0),
        ]
        assert report.total_duration_ms == pytest.approx(250.0)

    @pytest.mark.asyncio
    async def test_internal_error_still_returns_empty_report(self, mock_settings):
        with patch(
            "backend.services.cache_warming.get_settings", return_value=mock_settings, autospec=True
        ):
            warmer = CacheWarmer(strategy=WarmingStrategy.PARALLEL)
            warmer._warm_parallel = AsyncMock(side_effect=RuntimeError("boom"))
            report = await warmer.warm_all()

        # kills wa__24 (results=None → TypeError building/logging the report)
        assert report.results == []

    @pytest.mark.asyncio
    async def test_disabled_report_keeps_strategy(self, mock_settings):
        mock_settings.cache_warming_enabled = False
        with patch(
            "backend.services.cache_warming.get_settings", return_value=mock_settings, autospec=True
        ):
            warmer = CacheWarmer(strategy=WarmingStrategy.SEQUENTIAL)
            report = await warmer.warm_all()

        # kills wa__7 (strategy=None on the disabled-branch report)
        assert report.strategy is WarmingStrategy.SEQUENTIAL
```

### D2 — test_warm_cameras_writes_expected_cache_entry (kills clusters 10 + 11)

Replaces the bare `assert_called_once()` at :370-371 with the full call contract (kept as a new test alongside the existing one).

```python
class TestCameraWarmContract:
    @pytest.mark.asyncio
    async def test_warm_cameras_writes_expected_cache_entry(self, mock_settings):
        mock_camera = MagicMock()
        mock_camera.id = "cam1"
        mock_camera.name = "Camera 1"
        mock_camera.folder_path = "/path/to/cam1"
        mock_camera.status = "online"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_camera]

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.return_value = mock_session
        mock_session_cm.__aexit__.return_value = None

        mock_cache = AsyncMock()

        with (
            patch(
                "backend.services.cache_warming.get_settings",
                return_value=mock_settings,
                autospec=True,
            ),
            patch("backend.core.database.get_session", return_value=mock_session_cm, autospec=True),
            patch(
                "backend.services.cache_service.get_cache_service",
                return_value=mock_cache,
                autospec=True,
            ),
        ):
            warmer = CacheWarmer()
            count = await warmer._warm_cameras()

        assert count == 1

        # kills wc__16/_19/_22/_23 (key None/dropped/renamed); wc__19/_20 break the
        # 2-tuple unpack entirely, which fails the test
        key, payload = mock_cache.set.call_args[0]
        assert key == "cameras:list"
        # kills wc__7 (payload None), wc__17/_20 (value None/dropped),
        # wc__8.._15 (payload dict key renames)
        assert payload == [
            {
                "id": "cam1",
                "name": "Camera 1",
                "folder_path": "/path/to/cam1",
                "status": "online",
            }
        ]
        # kills wc__18 (ttl=None), wc__21 (ttl dropped)
        assert mock_cache.set.call_args.kwargs == {"ttl": 300}

        # kills wc__4 (execute(None) → str() has no "camera"), wc__5 (select(None))
        statement = mock_session.execute.call_args[0][0]
        assert "camera" in str(statement).lower()
```

### D3 — test_get_cache_warmer_propagates_settings (kills cluster 14)

Non-default config is required: the mutants are invisible under `"parallel"`/`30.0` because those coincide with the code defaults.

```python
class TestSingletonConfig:
    @pytest.mark.asyncio
    async def test_get_cache_warmer_propagates_settings(self, mock_settings):
        await reset_cache_warmer()
        mock_settings.cache_warming_strategy = "sequential"
        mock_settings.cache_warming_timeout = 7.5

        with patch(
            "backend.services.cache_warming.get_settings", return_value=mock_settings, autospec=True
        ):
            warmer = await get_cache_warmer()

        # kills gcw__3/_6/_8 (strategy None / kwarg dropped → PARALLEL)
        assert warmer._strategy is WarmingStrategy.SEQUENTIAL
        # kills gcw__7 (timeout None), gcw__9 (kwarg dropped → 30.0)
        assert warmer._timeout == 7.5
        await reset_cache_warmer()
```

### D4 — TestWarmingResultFields (kills clusters 5 + 6)

```python
class TestWarmingResultFields:
    @pytest.mark.asyncio
    async def test_parallel_success_and_failure_fields_accurate(self, mock_settings):
        async def ok_warmer():
            return 5

        async def bad_warmer():
            raise ValueError("Test error")

        with patch(
            "backend.services.cache_warming.get_settings", return_value=mock_settings, autospec=True
        ):
            warmer = CacheWarmer(strategy=WarmingStrategy.PARALLEL)
            warmer.register_warmer("success", ok_warmer)
            warmer.register_warmer("failure", bad_warmer)
            report = await warmer.warm_all()

        # kills wp__11, wp__38, wp__49 (cache_name=None incl. call-site variant)
        assert [r.cache_name for r in report.results] == ["success", "failure"]
        ok_result, bad_result = report.results
        assert ok_result.success is True
        # kills wp__39 (success=None is falsy; `is False` is not)
        assert bad_result.success is False
        assert isinstance(ok_result.duration_ms, float)
        assert isinstance(bad_result.duration_ms, float)

    @pytest.mark.asyncio
    async def test_timeout_result_fields(self, mock_settings):
        async def slow_warmer():
            await asyncio.sleep(10)
            return 5

        with patch(
            "backend.services.cache_warming.get_settings", return_value=mock_settings, autospec=True
        ):
            warmer = CacheWarmer(strategy=WarmingStrategy.PARALLEL, timeout_seconds=0.1)
            warmer.register_warmer("slow", slow_warmer)
            report = await warmer.warm_all()

        result = report.results[0]
        assert result.cache_name == "slow"          # kills wp__24
        assert result.success is False              # kills wp__25
        assert isinstance(result.duration_ms, float)  # kills wp__20, wp__26 (the duration None variants)
        assert "Timeout" in result.error

    @pytest.mark.asyncio
    async def test_sequential_result_fields_and_items(self, mock_settings):
        async def warm_a():
            return 5

        async def warm_b():
            return 10

        with patch(
            "backend.services.cache_warming.get_settings", return_value=mock_settings, autospec=True
        ):
            warmer = CacheWarmer(strategy=WarmingStrategy.SEQUENTIAL)
            warmer.register_warmer("cache1", warm_a)
            warmer.register_warmer("cache2", warm_b)
            report = await warmer.warm_all()

        # kills ws__13 (cache_name=None)
        assert [r.cache_name for r in report.results] == ["cache1", "cache2"]
        # kills ws__20 (items_cached=items dropped → total 0)
        assert report.total_items_cached == 15
        # kills ws__15 (duration_ms=None)
        assert all(isinstance(r.duration_ms, float) for r in report.results)
```

Note on wp__21/_23 and ws timeout/exception-branch `/1000`,`+`,`*1001` tweaks: `isinstance` catches only the `None` variants. They are already inside cluster 4's count; to fold them into green coverage, mirror D1's fake-clock setup with a sleeping warmer (UNVERIFIED complexity — acceptable to leave; a single exact-duration-per-branch test each, same clock trick, kills them).

### D5 — test_warm_system_status_payload_and_ttl (kills cluster 12)

```python
class TestSystemStatusContract:
    @pytest.mark.asyncio
    async def test_warm_system_status_payload_and_ttl(self, mock_settings):
        mock_cache = AsyncMock()

        with (
            patch(
                "backend.services.cache_warming.get_settings",
                return_value=mock_settings,
                autospec=True,
            ),
            patch(
                "backend.services.cache_service.get_cache_service",
                return_value=mock_cache,
                autospec=True,
            ),
        ):
            warmer = CacheWarmer()
            count = await warmer._warm_system_status()

        assert count == 1
        call_args = mock_cache.set.call_args
        data = call_args[0][1]
        # kills wss__8/_9 (environment renamed)
        assert data["environment"] == "test"
        # kills wss__10/_11 (warmed_at renamed)
        assert isinstance(data["warmed_at"], float)
        # kills wss__17 (ttl=None), wss__20 (ttl dropped)
        assert call_args.kwargs == {"ttl": 300}
```

### D6 — test_sequential_timeout_marks_warmer_failed (kills cluster 9)

```python
class TestSequentialTimeout:
    @pytest.mark.asyncio
    async def test_sequential_timeout_marks_warmer_failed(self, mock_settings):
        async def slow_warmer():
            await asyncio.sleep(0.5)
            return 5

        with patch(
            "backend.services.cache_warming.get_settings", return_value=mock_settings, autospec=True
        ):
            warmer = CacheWarmer(strategy=WarmingStrategy.SEQUENTIAL, timeout_seconds=0.1)
            warmer.register_warmer("slow", slow_warmer)
            report = await warmer.warm_all()

        # kills ws__5 (timeout=None → warmer completes in 0.5s → failed_count == 0)
        assert report.failed_count == 1
        assert report.results[0].cache_name == "slow"
        assert "Timeout" in report.results[0].error
```

### Bonus B1 — cluster 13 (3-line append to existing test at :316)

```python
        # inside test_register_default_warmers, after the name assertions:
        warmers = dict(warmer._warmers)
        assert warmers["cameras"] == warmer._warm_cameras          # kills rdw__2
        assert warmers["system_status"] == warmer._warm_system_status  # kills rdw__8
        assert warmers["alert_rules"] == warmer._warm_alert_rules      # kills rdw__14
```

## Coverage math for the drafted set

D1 kills 29 (cl.4×24 + cl.7×2 + cl.8×1, minus wp__21/_23 arithmetic deferred: +2 deferred → 27 solid, 2 foldable). D2 kills 19. D3 kills 5. D4 kills 8. D5 kills 6. D6 kills 1. B1 kills 3. Drafted coverage ≈ **69-71 of 100**; remaining 29-31 are clusters 1-3 (EQUIVALENT/LOW-VALUE, 31 keys — not worth asserting).

## Caveats

- All drafts UNVERIFIED (no pytest run per run-lock constraint). D1's exact-ms asserts depend on the fake clock's tick budget matching the four instrumented `perf_counter` calls; if `backend.core.logging` internals call `perf_counter` during the patched window, switch to per-call-pair capture or `>= 0` plus a `< 1000` upper bound (still kills /1000, +start, None; *1001 would then need the exact form).
- `str(select(None))` (wc__5) may raise ArgumentError instead of returning a string — either way the test fails on the mutant, which is the kill.
- 4 keys in the meta are still `null` (not yet checked) and are outside this triage.
