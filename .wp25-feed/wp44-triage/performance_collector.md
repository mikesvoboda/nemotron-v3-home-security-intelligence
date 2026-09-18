# WP4.4 Triage Dossier — backend/services/performance_collector.py

- **Survivors:** 107 of 1170 keys (exit_code 0 in `mutants/backend/services/performance_collector.py.meta`)
- **Diff source:** `uv run mutmut show <key>` (all 107 fetched successfully; no fallback diffing needed)
- **Covering test file (all clusters):** `backend/tests/unit/services/test_performance_collector.py`
  - `TestHealthChecks` L1565–1685 (`_check_postgres_health`, `_check_redis_health`)
  - `TestThroughputCalculation` L1098–1276 (`_get_detections_per_minute`, `_get_events_per_minute`)
  - `TestCollectRedisMetrics` L535–606
  - `TestCollectYolo26Metrics` L889–972
  - `TestCollectGpuMetrics` L336–381
- **Cluster totals:** TEST-GAP 70, EQUIVALENT 37, LOW-VALUE 0 (sum = 107)

## Key structural facts used for classification

- `ContainerMetrics` (backend/api/schemas/performance.py): `name`/`status`/`health` are required `str` — passing `None` or omitting raises `ValidationError`. In `_check_postgres_health`/`_check_redis_health`/`collect_redis_metrics` those raises are swallowed by the function's own outer `except Exception`, which returns the *same* fallback object the original branch returns → externally indistinguishable → EQUIVALENT.
- `RedisMetrics`: all five fields required (`connected_clients`/`blocked_clients` int `ge=0`, `hit_ratio` float `0..100`).
- No test in the file uses `caplog` → every logger-arg/log-text mutant is EQUIVALENT.
- The throughput tests mock `session` with `AsyncMock`: `session.execute(...)` returns a canned scalar **regardless of the query passed**, so every mutation to the query expression or cutoff value is invisible unless a test inspects the captured statement (this is the single biggest gap: 16+ mutants).
- Existing tests mock success paths with *complete* payload dicts and *benign* values (all-zero `blocked_clients`, `hits>misses`, counts divisible by 5), which makes all "missing-field default" and "edge value" mutants invisible.

## Cluster table

| # | Pattern | Count | Classification | Example keys (suffix) | Notes |
|---|---------|-------|----------------|----------------------|-------|
| 1 | `collect_redis_metrics`: `info.get(k, 0)` default flipped to `None`/omitted/`1` for keyspace_hits / keyspace_misses / connected_clients / used_memory / blocked_clients | 15 | TEST-GAP | `collect_redis_metrics__mutmut_27`, `…_32`, `…_59` | Keys: 27,29,32,35,37,40,54,56,59,62,64,67,70,72,75. Success test (test_performance_collector.py:562) always supplies every key, so defaults never fire. Sparse-info dict kills all 15 (drafted, T2). |
| 2 | `collect_yolo26_metrics`: defaults for missing health-response fields (`vram_gb`/`model`/`device`) flipped (None/omitted/`1`/"YOLO26"/"XXunknownXX"…) | 11 | TEST-GAP | `collect_yolo26_metrics__mutmut_28`, `…_35`, `…_41` | Keys: 28,30,33,35,37,40,41,43,45,48,49. Healthy test (L893) always supplies all fields. Missing-field test kills all 11 (drafted, T4). |
| 3 | `_check_postgres_health`+`_check_redis_health`: required ContainerMetrics field set to `None` or kwarg dropped in the not-None-client early return | 12 | EQUIVALENT | `_check_postgres_health__mutmut_3`, `_check_redis_health__mutmut_6`, `_check_postgres_health__mutmut_7` | Keys: pg 3,4,5,6,7,8 + rh 3,4,5,6,7,8. ValidationError → outer `except Exception` → returns the identical `{name, unknown, unhealthy}` fallback. Externally undetectable in principle. |
| 4 | `collect_redis_metrics`: required-field `None`/kwarg-drop inside the `RuntimeError` unreachable return | 10 | EQUIVALENT | `collect_redis_metrics__mutmut_5`, `…_11`, `…_14` | Keys: 5,6,7,8,9,10,11,12,13,14. Same pydantic-crash → outer catch → identical fallback reasoning. |
| 5 | Log-only mutations: `logger.warning/debug(None)`, message-slice and in-message arithmetic tweaks (`logger.debug(f"Redis metrics… {used_memory/(1024*1024)…}")` variants) | 13 | EQUIVALENT | `_check_postgres_health__mutmut_31`, `collect_redis_metrics__mutmut_77`, `collect_yolo26_metrics__mutmut_50` | Keys: pg31, rh28, dpm22, epm22, redis 4,22,24,76,77,78,79,80, yolo50. No test asserts logs (no caplog anywhere in the file). 77–80 mutate only the arithmetic *inside a debug f-string*. |
| 6 | Throughput query construction: whole `select(...)` / `.where(...)` / `func.count(...)` args replaced with `None`, or `detected_at/started_at >= cutoff` flipped to `>` | 10 | TEST-GAP | `_get_detections_per_minute__mutmut_11`, `…_8`, `_get_events_per_minute__mutmut_10` | Keys: dpm 7,8,9,10,11 + epm 7,8,9,10,11. Canonical comparison-operator flip on a freshness predicate — invisible because `session.execute` is an AsyncMock returning a canned scalar. Drafted T1 asserts the compiled SQL. |
| 7 | Throughput cutoff arithmetic: `now(UTC) - timedelta(minutes=5)` → `+ timedelta(5)` / `datetime.now(None)` (naive) / `minutes=6` | 6 | TEST-GAP | `_get_detections_per_minute__mutmut_2`, `…_3`, `…_5` | Keys: dpm 2,3,5 + epm 2,3,5. Wrong window silently zeroes (or biases) the throughput metric. Drafted T1 asserts cutoff is tz-aware and ≈ now−300s. |
| 8 | `hit_ratio` guard expression: `… if (hits+misses) > 0 else 0` → `or True` / `(hits-misses) > 0` / `>= 0` / `> 1` / else-branch `1` | 5 | TEST-GAP | `collect_redis_metrics__mutmut_43`, `…_48`, `…_51` | Keys: 43,48,49,50,51. Test only uses hits=100/misses=10; zero-traffic, misses>hits, and total==1 cases unasserted (zero-traffic crash → whole status flips to "unreachable"). Drafted T3. |
| 9 | Health-check `except`-branch `status="unknown"` → `"UNKNOWN"` / `"XXunknownXX"` (postgres + redis) | 4 | TEST-GAP | `_check_postgres_health__mutmut_40`, `_check_redis_health__mutmut_38` | Keys: pg 40,41 + rh 37,38. Exception-path tests (L1610, L1671) assert `name` and `health` but never `status`. Drafted T5. |
| 10 | Throughput `round(count/5.0, 1)` ndigits → `None`/removed (returns int via banker's rounding) | 4 | TEST-GAP | `_get_detections_per_minute__mutmut_16`, `…_18`, `_get_events_per_minute__mutmut_16` | Keys: dpm 16,18 + epm 16,18. `round(30.2, None)==30`. Existing tests use counts 150/25 (exact one-decimal values) so int-vs-float is invisible. Drafted T6 (count 151 → 30.2). |
| 11 | `collect_yolo26_metrics` unreachable-fallback `model="yolo26"`/`device="unknown"` → string variants | 4 | TEST-GAP | `collect_yolo26_metrics__mutmut_62`, `…_64` | Keys: 62,63,64,65. `test_collect_yolo26_metrics_connection_error` (L954) asserts only `status` and `vram_gb`. One-line strengthening listed below. |
| 12 | `_check_postgres_health` probe: `session.execute(text("SELECT 1"))` → `execute(None)` / `"XXSELECT 1XX"` / `"select 1"` | 3 | TEST-GAP | `_check_postgres_health__mutmut_15`, `…_17` | Success test (L1569) never asserts what was executed — the entire liveness-probe contract is unasserted. (`"select 1"` is equivalent on real Postgres but only killable via exact-string assert.) Drafted T5. |
| 13 | `collect_redis_metrics` RuntimeError branch: zeroed fields → `1` (`memory_mb=1`, `hit_ratio=1`, `blocked_clients=1`) | 3 | TEST-GAP | `collect_redis_metrics__mutmut_18`, `…_20` | Keys: 18,19,20. `test_collect_redis_metrics_not_connected` asserts only `status` and `connected_clients`. One-line strengthening below. |
| 14 | `collect_redis_metrics`: `info.get("blocked_clients", 0)` key string → `None`/`"XXblocked_clientsXX"`/`"BLOCKED_CLIENTS"` | 3 | TEST-GAP | `collect_redis_metrics__mutmut_69`, `…_73` | Keys: 69,73,74. Success test uses `blocked_clients: 0`, indistinguishable from the fallback 0 — needs a nonzero value (drafted T2). |
| 15 | `collect_gpu_metrics`: `data = self._collect_gpu_pynvml()` → `data = None` (pynvml path dead, always fallback) | 1 | TEST-GAP | `collect_gpu_metrics__mutmut_1` | The only covering test forces `_pynvml_available=False`, so pynvml-preference is unasserted. One-line test listed below. |
| 16 | `collect_yolo26_metrics`: `client.get(f"{yolo26_url}/health")` → `get(None)` | 1 | TEST-GAP | `collect_yolo26_metrics__mutmut_3` | AsyncMock happily receives `None`; no test asserts the request URL. Killed by URL assert in drafted T4. |
| 17 | Throughput `round(…, 1)` → `round(…, 2)` | 2 | EQUIVALENT | `_get_detections_per_minute__mutmut_21`, `_get_events_per_minute__mutmut_21` | `int/5.0` has at most one decimal digit, so rounding to 2 places is an identity. Truly semantic no-op. |

**Sums:** TEST-GAP = 15+11+10+6+5+4+4+3+3+3+1+1 = **70**; EQUIVALENT = 12+10+13+2 = **37**; total **107**. ✔

## Drafted tests (UNVERIFIED — not yet run red/green)

All target `backend/tests/unit/services/test_performance_collector.py`; style follows the existing file (`patch(...get_settings, autospec=True)` wrapper, `@pytest.mark.asyncio`, class grouping). Extra top-level import needed: `from datetime import UTC, datetime`.

TDD procedure (same for all): add the test against the mutant copy's line (assert fails on the mutant diff), then run against the original source and it passes; each test is red-on-mutant / green-on-original.

### T1 — kills clusters #6 (query construction, 10) and #7 (cutoff arithmetic, 6)

```python
class TestThroughputQueryContract:
    """Assert the throughput queries actually built (session.execute is otherwise mocked blind)."""

    @pytest.mark.asyncio
    async def test_get_detections_per_minute_builds_five_minute_cutoff_query(self) -> None:
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock()

            collector = PerformanceCollector()

            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar.return_value = 150
            mock_session.execute.return_value = mock_result

            result = await collector._get_detections_per_minute(mock_session)
            assert result == 30.0

            stmt = mock_session.execute.call_args.args[0]
            compiled = stmt.compile()
            sql = str(compiled).lower()

            # projection + predicate contract (kills count(None)/select(None)/where(None)/'> ' flip)
            assert "count(detections.id)" in sql
            assert "detected_at >=" in sql

            # cutoff contract: tz-aware, five minutes in the past
            cutoff = next(v for v in compiled.params.values() if hasattr(v, "utcoffset"))
            assert cutoff.utcoffset() is not None  # kills datetime.now(None)
            delta = (datetime.now(UTC) - cutoff).total_seconds()
            assert 270 <= delta <= 330  # kills +timedelta(5) and minutes=6

    @pytest.mark.asyncio
    async def test_get_events_per_minute_builds_five_minute_cutoff_query(self) -> None:
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock()

            collector = PerformanceCollector()

            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar.return_value = 25
            mock_session.execute.return_value = mock_result

            result = await collector._get_events_per_minute(mock_session)
            assert result == 5.0

            stmt = mock_session.execute.call_args.args[0]
            compiled = stmt.compile()
            sql = str(compiled).lower()

            assert "count(events.id)" in sql
            assert "started_at >=" in sql

            cutoff = next(v for v in compiled.params.values() if hasattr(v, "utcoffset"))
            assert cutoff.utcoffset() is not None
            delta = (datetime.now(UTC) - cutoff).total_seconds()
            assert 270 <= delta <= 330
```

// UNVERIFIED - not yet run red/green

### T2 — kills cluster #1 (redis info.get defaults, 15) and #14 (blocked_clients key, 3)

```python
class TestRedisInfoDefaults:
    """info() payloads that omit keys — the defensive-default contract is currently unasserted."""

    async def _collect_with_info(self, info: dict) -> "object":
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock()

            with patch("backend.core.redis.init_redis", autospec=True) as mock_init_redis:
                mock_raw_client = MagicMock()

                async def mock_info():
                    return info

                mock_raw_client.info = mock_info
                mock_client = MagicMock()
                mock_client._ensure_connected.return_value = mock_raw_client
                mock_init_redis.return_value = mock_client

                collector = PerformanceCollector()
                return await collector.collect_redis_metrics()

    @pytest.mark.asyncio
    async def test_collect_redis_metrics_sparse_info_uses_documented_defaults(self) -> None:
        # Fully-sparse payload: every missing key must fall back to 0, status stays healthy.
        result = await self._collect_with_info({})
        assert result is not None
        assert result.status == "healthy"
        assert result.connected_clients == 0
        assert result.memory_mb == 0.0
        assert result.hit_ratio == 0
        assert result.blocked_clients == 0

        # hits-only: misses defaults to 0 → 100% ratio (kills misses-default=1 and blocked/clients=1)
        result = await self._collect_with_info({"keyspace_hits": 30})
        assert result.status == "healthy"
        assert result.hit_ratio == 100.0

        # misses-only: hits defaults to 0 → 0% ratio (kills hits-default=1 → 1/(1+10)≈9.09)
        result = await self._collect_with_info({"keyspace_misses": 10})
        assert result.status == "healthy"
        assert result.hit_ratio == 0

    @pytest.mark.asyncio
    async def test_collect_redis_metrics_reports_nonzero_blocked_clients(self) -> None:
        # blocked_clients != 0 distinguishes the real key from None/"XXblocked_clientsXX"/"BLOCKED_CLIENTS"
        result = await self._collect_with_info(
            {
                "connected_clients": 5,
                "used_memory": 10 * 1024 * 1024,
                "keyspace_hits": 100,
                "keyspace_misses": 10,
                "blocked_clients": 3,
            }
        )
        assert result.blocked_clients == 3
```

// UNVERIFIED - not yet run red/green

### T3 — kills cluster #8 (hit_ratio guard expression, 5)

```python
class TestRedisHitRatioEdgeCases:
    """Hit-ratio guard branches: zero traffic, misses>hits, total==1."""

    async def _ratio(self, hits: int, misses: int) -> float:
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock()

            with patch("backend.core.redis.init_redis", autospec=True) as mock_init_redis:
                mock_raw_client = MagicMock()

                async def mock_info():
                    return {
                        "connected_clients": 1,
                        "used_memory": 1024 * 1024,
                        "keyspace_hits": hits,
                        "keyspace_misses": misses,
                        "blocked_clients": 0,
                    }

                mock_raw_client.info = mock_info
                mock_client = MagicMock()
                mock_client._ensure_connected.return_value = mock_raw_client
                mock_init_redis.return_value = mock_client

                collector = PerformanceCollector()
                result = await collector.collect_redis_metrics()
                assert result.status == "healthy"  # `or True` / `>= 0` mutants crash on zero traffic
                return result.hit_ratio

    @pytest.mark.asyncio
    async def test_zero_traffic_yields_zero_ratio_not_crash(self) -> None:
        assert await self._ratio(0, 0) == 0  # kills 43/49 (ZeroDivisionError→unreachable) and 51 (else=1)

    @pytest.mark.asyncio
    async def test_misses_exceed_hits_still_computes_ratio(self) -> None:
        assert abs(await self._ratio(10, 90) - 10.0) < 0.001  # kills 48 (hits-misses guard → 0)

    @pytest.mark.asyncio
    async def test_single_hit_computes_full_ratio(self) -> None:
        assert await self._ratio(1, 0) == 100.0  # kills 50 (total>1 guard → 0)
```

// UNVERIFIED - not yet run red/green

### T4 — kills cluster #2 (yolo26 field defaults, 11) and #16 (URL→None, 1)

```python
class TestCollectYolo26MissingFields:
    """Health endpoint returning {} must fall back to documented defaults on the healthy path."""

    @pytest.mark.asyncio
    async def test_collect_yolo26_metrics_missing_fields_use_defaults(self) -> None:
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock(yolo26_url="http://ai-yolo26:8095")

            collector = PerformanceCollector()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {}  # every field missing

            with patch.object(collector, "_get_http_client", autospec=True) as mock_get_client:
                mock_client = AsyncMock()
                mock_client.get.return_value = mock_response
                mock_get_client.return_value = mock_client

                result = await collector.collect_yolo26_metrics()

                # request-URL contract (kills get(None))
                mock_client.get.assert_called_once_with("http://ai-yolo26:8095/health")

                assert result is not None
                # None-defaults would ValidationError -> unreachable fallback; string tweaks
                # mutate model/device below.
                assert result.status == "unhealthy"  # status missing != "healthy"
                assert result.vram_gb == 0
                assert result.model == "yolo26"
                assert result.device == "unknown"
```

// UNVERIFIED - not yet run red/green

### T5 — kills cluster #9 (health except-branch status, 4) and #12 (pg probe string, 3)

```python
class TestHealthCheckContract:
    """Exception paths must report lowercase status='unknown', and the pg probe must run SELECT 1."""

    @pytest.mark.asyncio
    async def test_check_postgres_health_executes_select_one_probe(self) -> None:
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock()

            with patch("backend.core.database.get_session_factory", autospec=True) as mock_factory:
                mock_session = AsyncMock()
                mock_session.__aenter__.return_value = mock_session
                mock_session.__aexit__.return_value = None
                mock_session.execute = AsyncMock()
                mock_factory.return_value = lambda: mock_session

                collector = PerformanceCollector()
                result = await collector._check_postgres_health()

                assert result.health == "healthy"
                probe = mock_session.execute.await_args.args[0]
                # exact match: kills execute(None) and "XXSELECT 1XX" / "select 1" variants
                assert str(probe) == "SELECT 1"

    @pytest.mark.asyncio
    async def test_check_postgres_health_exception_status_is_unknown(self) -> None:
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock()

            with patch("backend.core.database.get_session_factory", autospec=True) as mock_factory:
                mock_session = AsyncMock()
                mock_session.__aenter__.side_effect = Exception("DB error")
                mock_factory.return_value = lambda: mock_session

                collector = PerformanceCollector()
                result = await collector._check_postgres_health()

                assert result.name == "postgres"
                assert result.status == "unknown"  # kills "UNKNOWN" / "XXunknownXX"
                assert result.health == "unhealthy"

    @pytest.mark.asyncio
    async def test_check_redis_health_exception_status_is_unknown(self) -> None:
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock()

            with patch("backend.core.redis.init_redis", autospec=True) as mock_init:
                mock_init.side_effect = Exception("Redis error")

                collector = PerformanceCollector()
                result = await collector._check_redis_health()

                assert result.name == "redis"
                assert result.status == "unknown"  # kills "UNKNOWN" / "XXunknownXX"
                assert result.health == "unhealthy"
```

// UNVERIFIED - not yet run red/green

### T6 — kills cluster #10 (round ndigits → None/removal, 4)

```python
class TestThroughputRounding:
    """Counts that are NOT multiples of 5 expose int-vs-float (round(x, None) drops the decimal)."""

    @pytest.mark.asyncio
    async def test_get_detections_per_minute_preserves_one_decimal(self) -> None:
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock()

            collector = PerformanceCollector()

            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar.return_value = 151  # 151/5 = 30.2 — not exactly representable as int
            mock_session.execute.return_value = mock_result

            result = await collector._get_detections_per_minute(mock_session)

            assert isinstance(result, float)
            assert result == 30.2  # round(30.2, None) == 30 fails this

    @pytest.mark.asyncio
    async def test_get_events_per_minute_preserves_one_decimal(self) -> None:
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock()

            collector = PerformanceCollector()

            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar.return_value = 27  # 27/5 = 5.4
            mock_session.execute.return_value = mock_result

            result = await collector._get_events_per_minute(mock_session)

            assert isinstance(result, float)
            assert result == 5.4
```

// UNVERIFIED - not yet run red/green

## Remaining TEST-GAP clusters — one-line strengthenings (not drafted)

- **#13** (`collect_redis_metrics` RuntimeError zeros→1): in `test_collect_redis_metrics_not_connected` (L539) add `assert result.memory_mb == 0 and result.hit_ratio == 0 and result.blocked_clients == 0`.
- **#11** (yolo26 unreachable fallback strings): in `test_collect_yolo26_metrics_connection_error` (L954) add `assert result.model == "yolo26" and result.device == "unknown"`.
- **#15** (pynvml bypass): new test — `collector._pynvml_available = True`, patch `collector._collect_gpu_pynvml` to return a valid dict and `collector._collect_gpu_fallback` to an AsyncMock; assert the returned `GpuMetrics` fields come from pynvml and `fallback.assert_not_awaited()`.

## Kill coverage of drafted tests

T1: 16 · T2: 18 · T3: 5 · T4: 12 · T5: 7 · T6: 4 → **62 / 70 TEST-GAP mutants**; remaining 8 via the three one-line strengthenings above.
