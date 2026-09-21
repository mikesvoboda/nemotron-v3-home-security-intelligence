# WP4.4 Triage Dossier — backend/services/performance_collector.py

Generated: 2026-09-18 (read-only triage wave; no tests executed, no repo files touched).
Pipeline: `mutants/backend/services/performance_collector.py.meta` → 341 SURVIVED keys
(exit_code 0) → per-variant diff vs `__mutmut_orig` bodies in the trampoline copy
(`mutants/backend/services/performance_collector.py`), cross-checked with
`uv run mutmut show` (read-only, worked fine; two spot-checks matched byte-for-byte).
Covering tests from `mutants/mutmut-stats.json::tests_by_mangled_function_name`.

**Totals: 341 survivors = 258 TEST-GAP + 80 EQUIVALENT + 3 LOW-VALUE.**

## Covering test file(s)

- `backend/tests/unit/services/test_performance_collector.py` — the only covering file
  (all 25 mangled functions; 242 test-refs). Key regions: thresholds :22-94,
  init :102-128, http client :131-161, gpu fallback :182-333, gpu metrics :336-381,
  host :389-489 & :2242-2305, postgres :497-527 & :2313-2436, redis :535-606,
  container health :614-760, alerts :768-881 & :1284-1557, yolo26 :889-972,
  nemotron :980-1090, throughput helpers :1098-1217, health checks :1565-1685,
  close :1693-1776, collect_all :1784-2036, pynvml :2044-2155, inference :2163-2234.
- `backend/tests/unit/services/test_system_broadcaster.py` / `test_system_broadcaster_history.py`
  — only touch `set_performance_collector` (different module), irrelevant here.

## Why so many survivors — the three structural reasons

1. **Logger args**: 43 mutants swap f-strings/`exc_info` for `None`/case variants. Nothing
   in the suite asserts on log records → EQUIVALENT at test level.
2. **Broad `except Exception` swallows the evidence**: mutants that make a return-path
   construct an invalid Pydantic model *raise inside the `try`* and fall into a handler
   returning the same values → observationally identical (this is why `name=None` etc. on
   the None-branch literals of `_check_postgres_health`/`_check_redis_health`/
   `collect_redis_metrics` survived despite tests asserting those exact fields — the
   mutated occurrence is the branch *inside* the try; the surviving field mutations are in
   the *except*-branch duplicates which the tests never assert). Verified via `mutmut show`
   line contexts + pydantic probes (`ContainerMetrics(name=None,...)` raises
   ValidationError → caught by `except Exception` → outer literal = original values).
3. **Mock-only happy paths**: tests mock `pynvml`/`httpx`/sessions with MagicMocks whose
   methods are `MagicMock()` (ignore any args, never validate) and payloads always contain
   every key with "round" values — so call-arg mutations, missing-key default mutations,
   sentinel/`or`-fallback mutations, and output-dict key mutations are never observed.

## Cluster table (38 clusters; counts sum to 341)

`T` = test-file evidence below. GAP-vs-weak-test notes name what the covering test misses.

| ID | Pattern (function/concern) | N | Class | Example keys (mutmut_#) |
|----|---------------------------|---|-------|--------------------------|
| C01 | logger call arg/text/exc_info mutations, module-wide (16 funcs: pg/redis/service health, gpu fb/pynvml, throughput, init, close, container, host, inference, nemotron, postgresql, redis, yolo26) | 43 | EQUIVALENT | check_service_health_9, collect_postgresql_metrics_51, collect_redis_metrics_77 |
| C02 | `_check_postgres/_check_redis_health` None-branch `ContainerMetrics(...)` arg mutations (name/status/health→None, kwarg removal) → ValidationError caught by outer except → same values returned | 12 | EQUIVALENT | _check_postgres_health_3..8, _check_redis_health_3..8 |
| C03 | `collect_redis_metrics` inner-unreachable `RedisMetrics` None/removed-field mutations → same swallow to identical outer-except literal | 10 | EQUIVALENT | collect_redis_metrics_5..14 |
| C04 | SQL literal case-only (`"SELECT…"` → `"select…"`) — SQL keywords case-insensitive | 2 | EQUIVALENT | _check_postgres_health_18, collect_postgresql_metrics_7 |
| C05 | `name.decode("utf-8")` → `"UTF-8"` — same codec | 1 | EQUIVALENT | _collect_gpu_pynvml_10 |
| C06a | `collect_host_metrics` memory/disk except-branch `0.0`→`1.0` normalization — identical after the `if x > 0 else 1.0` guard | 2 | EQUIVALENT | collect_host_metrics_22, _41 |
| C06b | `collect_host_metrics` guard `ram_total_gb > 0`→`> 1` / `disk_total_gb > 0`→`> 1` — changes real totals in (0,1] GB (sub-1GB container views) | 2 | TEST-GAP | collect_host_metrics_55, _60 |
| C07 | `__init__` `self._pynvml_available = False` pre-assignment overwritten by `_init_pynvml()` before any read | 2 | EQUIVALENT | __init___1, __init___2 |
| C08 | throughput `round(count/5.0, 1)`→`round(…, 2)` — n/5 is always exact at 1 dp → identical | 2 | EQUIVALENT | _get_detections_per_minute_21, _get_events_per_minute_21 |
| C09 | pynvml `power // 1000` → `/ 1000` — test mock uses integral mW (150000→150.0 coerced to int by pydantic); real GPUs report fractional W (124600 → 124.6 → GpuMetrics ValidationError → GPU metrics silently None) | 1 | TEST-GAP | _collect_gpu_pynvml_21 |
| C10 | `collect_container_health` `healthy_count` sum mutations — feeds only a debug log | 5 | EQUIVALENT | collect_container_health_54, _56, _57 |
| C11 | pg unreachable-fallback filler constants (`connections_max=31`, `cache_hit_ratio=1`, `transactions_per_min=1`) | 3 | LOW-VALUE | collect_postgresql_metrics_69, _70, _71 |
| C12 | alert-threshold boundary flips `>=`→`>` / `<`→`<=` across all alert checkers (gpu temp/vram warn+crit, host cpu/ram/disk warn+crit, redis mem/hit, pg conn-ratio) — existing tests only use values strictly beyond thresholds | 15 | TEST-GAP | check_gpu_alerts_3, check_host_alerts_61, check_redis_alerts_27 |
| C13 | pg alert payload arithmetic `value=conn_ratio*100`→`/100`/`*101`, `threshold=…*100`→`/100`/`*101` — alert payload value/threshold never asserted | 4 | TEST-GAP | check_postgresql_alerts_30, _31, _32 |
| C14 | pg conn-ratio zero-guard `else 0`→`else 1` — spurious critical at connections_max>0==1 | 1 | TEST-GAP | check_postgresql_alerts_9 |
| C15a | `collect_all` `timestamp=` arg removed → identical `default_factory=lambda: datetime.now(UTC)` | 1 | EQUIVALENT | collect_all_41 |
| C15b | `collect_all` `datetime.now(UTC)`→`datetime.now(None)` → naive timestamp (naive≠aware; pydantic keeps naive) — timestamp tz never asserted | 1 | TEST-GAP | collect_all_50 |
| C16 | `collect_gpu_metrics` `data = self._collect_gpu_pynvml()` → `data = None` — always uses fallback when pynvml works; test coverage for this function is only the fallback-path test | 1 | TEST-GAP | collect_gpu_metrics_1 |
| C17 | `_get_http_client` `timeout=5.0`→`None`/`6.0`/removed — client timeout never asserted | 2 | TEST-GAP | _get_http_client_4, _5 |
| C18 | `_init_pynvml` success branch `_pynvml_available = True`→`None`/`False` — success path never taken in tests (pynvml import fails in CI; test env HAS pynvml but nvmlInit fails, and no test stubs it) | 2 | TEST-GAP | _init_pynvml_1, _2 |
| C19 | `_init_pynvml` except branch `= False`→`None`/`True` — flag value never asserted (only `hasattr`) | 2 | TEST-GAP | _init_pynvml_7, _8 |
| C20 | `_collect_gpu_pynvml` nvml call-arg mutations (handle→None, index 0→1/None, GetName/Util/Mem/Power handle→None, temperature arg→None, GetPowerUsage arg→None) — `handle=MagicMock()` accepts anything, mocks ignore args | 9 | TEST-GAP | _collect_gpu_pynvml_2, _4, _16 |
| C21 | `_collect_gpu_fallback` missing-key defaults (`data.get(key, 0)`→None/1/removed/`get(None)`/key-case) + `vram_total_gb 24.0→25.0` + `client.get(None)` — tests never assert name/utilization/vram or the 24.0 assumption | 19 | TEST-GAP | _collect_gpu_fallback_10, _24, _38 |
| C22 | `collect_yolo26_metrics` missing-key defaults (vram/model/device→None/1/removed/`get(None)`/case) + unreachable-fallback model/device case + `client.get(None)` — success tests send every key | 16 | TEST-GAP | collect_yolo26_metrics_3, _35, _62 |
| C23 | `collect_nemotron_metrics` slot semantics: `s.get("state", 0)`→None/1/removed (missing-state = active/None-comparison), `slots[0]`→`slots[1]`, `n_ctx` default 4096→None/4097/removed, unreachable `context_size 0→1`, `client.get(None)` — state-less slots / n_ctx-mixed arrays / unreachable context never tested | 9 | TEST-GAP | collect_nemotron_metrics_11, _26, _54 |
| C24 | `collect_host_metrics` `psutil.disk_usage("/")`→`None`/`"XX/XX"` — autospec mock ignores the path arg | 2 | TEST-GAP | collect_host_metrics_24, _25 |
| C25 | `collect_container_health` service names/URLs/client-arg/backend-status mutations (`"frontend"→"FRONTEND"`, url→None/`rstrip(None)`/`lstrip('/')`, `client→None`, backend `status` case) — test asserts only len + result[0].name/health | 22 | TEST-GAP | collect_container_health_16, _42, _2 |
| C26 | `_check_service_health` `client.get(url→None, timeout=2.0→None/3.0/removed)` + branch output field content (status `XXrunningXX`/`RUNNING`, name/status/health→None, kwarg removal; None-invalid ones get re-swallowed by `except Exception` into status=unknown which the non-200 branch never asserts) | 14 | TEST-GAP | _check_service_health_2, _23, _28 |
| C26b | `_check_postgres_health`/`_check_redis_health` except-branch status case variants (`XXunknownXX`/`UNKNOWN`) + `session.execute(text("SELECT 1"))`→`None`/`XXSELECT 1XX` — except-branch tests assert name+health only | 6 | TEST-GAP | _check_postgres_health_15, _41, _check_redis_health_37 |
| C27 | `collect_postgresql_metrics` sentinel/fallback values never observed: sql literal `XXSELECT…XX`, `scalar() or 0/100.0/1` flips (`or 1`, `and 0`), execute-result→None, `txns=None` fallback (float(None) raises→unreachable), unreachable `connections_active=1` — healthy-path values (active/cache/txns) are never asserted from a real (mocked) query flow | 9 | TEST-GAP | collect_postgresql_metrics_11, _30, _31 |
| C28 | `collect_redis_metrics` `info.get(key, default)` default mutations (None/1/removed) and key mutations (`"XXblocked_clientsXX"`, case, `get(None)`) — test payload always has every key with default-hiding values | 18 | TEST-GAP | collect_redis_metrics_27, _69, _74 |
| C29 | `collect_redis_metrics` hit-ratio guard mutations (`> 0`→`or True`/`>= 0`/`> 1`, `else 0`→`1`, `hits+misses`→`hits-misses`) — zero-input and single-hit payloads never tested (ZeroDivisionError would flip healthy→unreachable) | 5 | TEST-GAP | collect_redis_metrics_43, _49, _50 |
| C30 | `collect_redis_metrics` unreachable-literal `memory_mb/hit_ratio/blocked_clients 0→1` — test asserts only status + connected_clients==0 | 3 | TEST-GAP | collect_redis_metrics_18, _19, _20 |
| C31 | throughput helpers: cutoff `now(UTC) ± timedelta`→plus (future window!), minutes 5→6, `datetime.now(None)` (tz-naive bound), where clause removal/`where(None)`/`count(None)`, `>=`→`>`, `round(…, 1)`→`round(…, None)`/removed (int truncation) — tests mock `session.execute` wholesale; the SQL and cutoff are never inspected; 150/25 scalar values hide int truncation | 20 | TEST-GAP | _get_detections_per_minute_2, _11, _16 |
| C32 | `collect_inference_metrics` `tracker.get_stage_stats("watch_to_detect"/"batch_to_analyze"/"total_pipeline", window_minutes=5)` call-arg mutations (None/case/XX/window 6/arg removal) — tracker is one MagicMock returning the same dict for every call; neither stage name, window, nor per-stage mapping asserted | 21 | TEST-GAP | collect_inference_metrics_3, _9, _22 |
| C33 | `collect_inference_metrics` throughput seeds `images_per_min/events_per_min = 0.0`→None/1.0 (DB-failure path → throughput None fails `dict[str,float]` → whole InferenceMetrics becomes None), helper session arg→None | 6 | TEST-GAP | collect_inference_metrics_26, _29, _31 |
| C34 | `collect_inference_metrics` latency contract: output keys `avg`/`p95`/`p99` case/XX, source keys `avg_ms`/`p95_ms`/`p99_ms` →None/XX/case, `or 0`→`or 1` — tests assert only 2 of 8 latency entries and never the key set | 42 | TEST-GAP | collect_inference_metrics_47, _51, _92 |
| C35 | `collect_inference_metrics` `queues={"detection": 0, "analysis": 0}` key/value mutations — queues never asserted anywhere | 6 | TEST-GAP | collect_inference_metrics_104, _106, _109 |

Sanity: EQUIVALENT = 43+12+10+2+1+2+2+2+1+5+1 = 80; LOW-VALUE = 3; TEST-GAP = 341−83 = 258. ✓

## Key TEST-GAP notes (what the covering test misses)

- **C12/C13/C14** (T: `TestAlertGeneration` :768-881, `TestAlertGenerationEdgeCases` :1284-1557):
  every alert test uses temperatures 78/90 vs thresholds 75/85, VRAM 91.6%/95.8% vs 90/95,
  cpu 98 vs 95, redis 550 vs 500, hit 5 vs 10, pg 96% vs 95% — no value equals a threshold,
  and no test asserts `alert.value` / `alert.threshold`. Exact-threshold fixtures kill all
  15 boundary flips (percent boundaries verified float-exact: 19/20, 9/10, 17/20, 4/5,
  95/100, 190/200 all hit exactly).
- **C16** (T: `TestCollectGpuMetrics` :336-381 — only exercises the fallback path).
- **C17** (T: `TestGetHttpClient` :131-161 — asserts creation + identity reuse only).
- **C18/C19** (T: `TestPerformanceCollectorInit` :102-128 — asserts `hasattr` only;
  pynvml is importable in the venv but `nvmlInit` fails → always the except path,
  and the flag value itself is never asserted).
- **C20** (T: `TestCollectGpuPynvmlSuccess` :2044-2155 — mocks `nvmlDevice*` with
  `MagicMock(return_value=…)`, so handle=None/index 1 pass unnoticed).
- **C21/C22/C23** (T: :182-333, :889-972, :980-1090 — payloads carry every key;
  `test_collect_gpu_fallback_handles_missing_values` omits only temperature/power, never
  device/utilization/vram; nemotron slots all share one `n_ctx`; state-less slots never sent).
- **C25/C26/C26b** (T: :614-760, :1565-1685 — `collect_container_health` asserts len 6 +
  `result[0].name/health`; `_check_service_health` asserts name/health/status but not the
  request URL/timeout or the `status` on non-200; health-check except branches assert
  name+health, not `status`).
- **C27/C28/C29/C30** (T: :535-606, :2313-2436 — redis success payload has all keys;
  pg healthy-path result values never asserted; unreachable tests assert status only).
- **C31** (T: `TestThroughputCalculation` :1098-1217 — `session.execute` mocked wholesale;
  the WHERE clause, cutoff tz/window, and rounding to 1 dp are invisible).
- **C32/C33/C34/C35** (T: :1219-1276, :2163-2234 — one tracker mock for all three stages;
  `missing_stats` test asserts only `yolo26.avg` and `nemotron.p95`; throughput mocked at
  the helper boundary; `queues` unasserted).

## Drafted kill-tests (UNVERIFIED — not yet run red/green)

TDD procedure for each: append to `backend/tests/unit/services/test_performance_collector.py`
→ must PASS against the original module → apply the cluster's one-line diff → the marked
assert must FAIL (mutant killed).

```python
# =============================================================================
# WP4.4 mutation-triage kill tests — UNVERIFIED - not yet run red/green
# =============================================================================
import operator
import sys
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.api.schemas.performance import (
    ContainerMetrics,
    DatabaseMetrics,
    GpuMetrics,
    HostMetrics,
    RedisMetrics,
)
from backend.services.performance_collector import PerformanceCollector


@contextmanager
def _stub_pynvml(stub):
    """Make `import pynvml` inside the service resolve to the stub."""
    with patch.dict(sys.modules, {"pynvml": stub}):
        yield


class TestAlertBoundaryAndPayload:
    """UNVERIFIED. Kills C12 (15 boundary flips), C13 (4 payload-arithmetic),
    C14 (1 zero-guard). Asserts the inclusive threshold boundary for every
    threshold pair plus the pg alert payload arithmetic."""

    def _collector(self):
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock()
            return PerformanceCollector()

    def test_gpu_temperature_alerts_at_exact_thresholds(self) -> None:
        collector = self._collector()
        warn = GpuMetrics(
            name="G", utilization=50.0, vram_used_gb=10.0, vram_total_gb=24.0,
            temperature=75, power_watts=150,
        )
        alerts = collector.check_gpu_alerts(warn)
        assert len(alerts) == 1 and alerts[0].severity == "warning"  # >= 75
        crit = GpuMetrics(
            name="G", utilization=50.0, vram_used_gb=10.0, vram_total_gb=24.0,
            temperature=85, power_watts=150,
        )
        alerts = collector.check_gpu_alerts(crit)
        assert len(alerts) == 1 and alerts[0].severity == "critical"  # >= 85

    def test_gpu_vram_alerts_at_exact_thresholds(self) -> None:
        collector = self._collector()
        warn = GpuMetrics(
            name="G", utilization=50.0, vram_used_gb=21.6, vram_total_gb=24.0,
            temperature=60, power_watts=150,
        )  # 21.6/24 == 90.0 exactly
        assert warn.vram_percent == 90.0
        alerts = collector.check_gpu_alerts(warn)
        assert len(alerts) == 1 and alerts[0].severity == "warning"
        crit = GpuMetrics(
            name="G", utilization=50.0, vram_used_gb=22.8, vram_total_gb=24.0,
            temperature=60, power_watts=150,
        )  # == 95.0 exactly
        assert crit.vram_percent == 95.0
        alerts = collector.check_gpu_alerts(crit)
        assert len(alerts) == 1 and alerts[0].severity == "critical"

    def test_host_alerts_at_exact_thresholds(self) -> None:
        collector = self._collector()
        warn = HostMetrics(
            cpu_percent=80.0, ram_used_gb=17.0, ram_total_gb=20.0,
            disk_used_gb=400.0, disk_total_gb=500.0,
        )  # ram 85.0 / disk 80.0 exact
        kinds = {(a.metric, a.severity) for a in collector.check_host_alerts(warn)}
        assert kinds == {("host_cpu", "warning"), ("host_ram", "warning"),
                         ("host_disk", "warning")}
        crit = HostMetrics(
            cpu_percent=95.0, ram_used_gb=19.0, ram_total_gb=20.0,
            disk_used_gb=450.0, disk_total_gb=500.0,
        )  # 95 / 95 / 90 exact
        kinds = {(a.metric, a.severity) for a in collector.check_host_alerts(crit)}
        assert kinds == {("host_cpu", "critical"), ("host_ram", "critical"),
                         ("host_disk", "critical")}

    def test_redis_alerts_at_exact_thresholds(self) -> None:
        collector = self._collector()
        mem = RedisMetrics(
            status="healthy", connected_clients=1, memory_mb=500.0,
            hit_ratio=90.0, blocked_clients=0,
        )
        assert any(a.metric == "redis_memory" and a.severity == "critical"
                   for a in collector.check_redis_alerts(mem))  # >= 500
        hit = RedisMetrics(
            status="healthy", connected_clients=1, memory_mb=10.0,
            hit_ratio=10.0, blocked_clients=0,
        )
        # `hit_ratio < 10` is exclusive at 10 — mutant `<=` would alert here
        assert collector.check_redis_alerts(hit) == []

    def test_pg_alerts_at_exact_boundary_and_payload(self) -> None:
        collector = self._collector()
        db = DatabaseMetrics(
            status="healthy", connections_active=19, connections_max=20,
            cache_hit_ratio=95.0, transactions_per_min=100,
        )  # ratio exactly 0.95 == critical
        alerts = collector.check_postgresql_alerts(db)
        conn = [a for a in alerts if a.metric == "pg_connections"]
        assert len(conn) == 1 and conn[0].severity == "critical"  # >= (kills C12)
        assert conn[0].value == 95.0  # kills C13 (*100 -> /100 or *101)
        assert conn[0].threshold == 95.0  # kills C13
        cache = DatabaseMetrics(
            status="healthy", connections_active=1, connections_max=20,
            cache_hit_ratio=80.0, transactions_per_min=100,
        )  # `cache_hit_ratio < 80` exclusive at 80 — mutant <= alerts here
        assert collector.check_postgresql_alerts(cache) == []

    def test_pg_conn_ratio_guard_bounds(self) -> None:
        collector = self._collector()
        zero = DatabaseMetrics(
            status="healthy", connections_active=0, connections_max=1,
            cache_hit_ratio=95.0, transactions_per_min=100,
        )
        assert collector.check_postgresql_alerts(zero) == []  # kills C14 (else 1)
        one = DatabaseMetrics(
            status="healthy", connections_active=1, connections_max=1,
            cache_hit_ratio=95.0, transactions_per_min=100,
        )  # guard `> 0`->`> 1` (C12) would report ratio 0, no alert
        assert any(a.metric == "pg_connections" and a.severity == "critical"
                   for a in collector.check_postgresql_alerts(one))


class TestCollectAllTimestampAndGpuSource:
    """UNVERIFIED. Kills C15b (naive timestamp), C16 (gpu pynvml bypass),
    C17 (http client timeout), C18/C19 (pynvml availability flag)."""

    @pytest.mark.asyncio
    async def test_collect_all_timestamp_is_aware_utc(self) -> None:
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock()
            collector = PerformanceCollector()
            with (
                patch.object(collector, "collect_gpu_metrics", return_value=None, autospec=True),
                patch.object(collector, "collect_yolo26_metrics", return_value=None, autospec=True),
                patch.object(collector, "collect_nemotron_metrics", return_value=None, autospec=True),
                patch.object(collector, "collect_host_metrics", return_value=None, autospec=True),
                patch.object(collector, "collect_postgresql_metrics", return_value=None, autospec=True),
                patch.object(collector, "collect_redis_metrics", return_value=None, autospec=True),
                patch.object(collector, "collect_container_health", return_value=[], autospec=True),
                patch.object(collector, "collect_inference_metrics", return_value=None, autospec=True),
            ):
                result = await collector.collect_all()
            assert isinstance(result.timestamp, datetime)
            assert result.timestamp.tzinfo is not None  # kills datetime.now(None)
            assert result.timestamp.utcoffset() == timedelta(0)

    @pytest.mark.asyncio
    async def test_collect_gpu_metrics_prefers_pynvml_over_fallback(self) -> None:
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock()
            collector = PerformanceCollector()
            with (
                patch.object(
                    collector, "_collect_gpu_pynvml",
                    return_value={
                        "name": "RTX", "utilization": 10.0, "vram_used_gb": 1.0,
                        "vram_total_gb": 2.0, "temperature": 65, "power_watts": 124,
                    },
                    autospec=True,
                ),
                patch.object(
                    collector, "_collect_gpu_fallback", return_value=None, autospec=True
                ) as mock_fallback,
            ):
                result = await collector.collect_gpu_metrics()
            assert result is not None
            assert result.temperature == 65
            assert mock_fallback.call_count == 0  # kills data = None (C16)

    @pytest.mark.asyncio
    async def test_default_http_client_timeout_is_5_seconds(self) -> None:
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock()
            collector = PerformanceCollector()
            client = await collector._get_http_client()
            try:
                assert client.timeout.connect == 5.0  # kills None / 6.0 (C17)
                assert client.timeout.read == 5.0
            finally:
                await client.aclose()

    def test_init_pynvml_success_sets_flag_true(self) -> None:
        stub = MagicMock()
        stub.nvmlInit.return_value = None
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock()
            with _stub_pynvml(stub):
                collector = PerformanceCollector()
            stub.nvmlInit.assert_called_once()
            assert collector._pynvml_available is True  # kills None / False (C18)

    def test_init_pynvml_failure_sets_flag_false(self) -> None:
        stub = MagicMock()
        stub.nvmlInit.side_effect = Exception("NVML down")
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock()
            with _stub_pynvml(stub):
                collector = PerformanceCollector()
            assert collector._pynvml_available is False  # kills None / True (C19)


class TestGpuPynvmlAndFallbackContract:
    """UNVERIFIED. Kills C20 (9 nvml arg mutants), C21 (19 fallback default
    mutants), C09 (integer power division), C06b (host >1 guard), C24 (disk path)."""

    def _gpu_stub(self):
        stub = MagicMock()
        stub.nvmlInit.return_value = None
        stub.NVML_TEMPERATURE_GPU = 42
        return stub

    def test_pynvml_queries_device_zero_with_handle(self) -> None:
        stub = self._gpu_stub()
        handle = MagicMock(name="handle")
        stub.nvmlDeviceGetHandleByIndex.return_value = handle
        stub.nvmlDeviceGetName.return_value = "Test GPU"
        stub.nvmlDeviceGetUtilizationRates.return_value = MagicMock(gpu=50, memory=60)
        stub.nvmlDeviceGetMemoryInfo.return_value = MagicMock(
            used=10 * 1024**3, total=24 * 1024**3
        )
        stub.nvmlDeviceGetTemperature.return_value = 65
        stub.nvmlDeviceGetPowerUsage.return_value = 124600  # fractional-watts mW
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock()
            with _stub_pynvml(stub):
                collector = PerformanceCollector()
                result = collector._collect_gpu_pynvml()
        assert result is not None
        assert stub.nvmlDeviceGetHandleByIndex.call_args.args[0] == 0  # index 0 only
        for fn in (
            stub.nvmlDeviceGetName,
            stub.nvmlDeviceGetUtilizationRates,
            stub.nvmlDeviceGetMemoryInfo,
            stub.nvmlDeviceGetPowerUsage,
        ):
            assert fn.call_args.args[0] is handle  # kills handle->None mutants
        assert stub.nvmlDeviceGetTemperature.call_args.args == (handle, 42)
        # // 1000 floor division: 124600 mW -> 124 W (mutant / 1000 -> 124.6)
        assert result["power_watts"] == 124  # kills C09

    @pytest.mark.asyncio
    async def test_gpu_fallback_defaults_when_keys_missing(self) -> None:
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock(yolo26_url="http://ai-yolo26:8095")
            collector = PerformanceCollector()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "healthy"}
            with patch.object(collector, "_get_http_client", autospec=True) as mock_get_client:
                mock_client = AsyncMock()
                mock_client.get.return_value = mock_response
                mock_get_client.return_value = mock_client
                result = await collector._collect_gpu_fallback()
                assert mock_client.get.call_args.args[0] == "http://ai-yolo26:8095/health"
            assert result == {  # full-dict equality kills every default mutant (C21)
                "name": "Unknown GPU",
                "utilization": 0,
                "vram_used_gb": 0,
                "vram_total_gb": 24.0,
                "temperature": 0,
                "power_watts": 0,
            }

    @pytest.mark.asyncio
    async def test_gpu_fallback_keeps_reported_values(self) -> None:
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock(yolo26_url="http://ai-yolo26:8095")
            collector = PerformanceCollector()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "device": "RTX A5500",
                "gpu_utilization": 45.5,
                "vram_used_gb": 12.3,
                "temperature": 65.7,
                "power_watts": 125.3,
            }
            with patch.object(collector, "_get_http_client", autospec=True) as mock_get_client:
                mock_client = AsyncMock()
                mock_client.get.return_value = mock_response
                mock_get_client.return_value = mock_client
                result = await collector._collect_gpu_fallback()
            # key-content mutants (GPU_UTILIZATION / XXvram_used_gbXX / get(None))
            # silently fall back to 0 - this assert pins the real keys
            assert result["name"] == "RTX A5500"
            assert result["utilization"] == 45.5
            assert result["vram_used_gb"] == 12.3

    @pytest.mark.asyncio
    async def test_host_metrics_reads_root_and_keeps_sub_gigabyte_totals(self) -> None:
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock()
            with patch(
                "backend.services.performance_collector.psutil", autospec=True
            ) as mock_psutil:
                mock_psutil.cpu_percent.return_value = 10.0
                mock_psutil.virtual_memory.return_value = MagicMock(
                    used=0.25 * 1024**3, total=0.5 * 1024**3  # < 1 GB view (containers)
                )
                mock_psutil.disk_usage.return_value = MagicMock(
                    used=0.1 * 1024**3, total=0.25 * 1024**3
                )
                collector = PerformanceCollector()
                result = await collector.collect_host_metrics()
                assert mock_psutil.disk_usage.call_args.args[0] == "/"  # kills C24
                assert result.ram_total_gb == 0.5  # kills guard > 1 (C06b)
                assert result.disk_total_gb == 0.25  # kills guard > 1 (C06b)


class TestContainerHealthWiring:
    """UNVERIFIED. Kills C25 (22 wiring mutants), C26 (14 service-check mutants),
    C26b (6 health-check mutants)."""

    @pytest.mark.asyncio
    async def test_container_health_wires_names_urls_and_client(self) -> None:
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock(
                frontend_url="http://frontend:8080/",
                yolo26_url="http://ai-yolo26:8095",
                nemotron_url="http://ai-llm:8091",
            )
            collector = PerformanceCollector()
            with (
                patch.object(collector, "_check_service_health", autospec=True) as mock_service,
                patch.object(collector, "_check_postgres_health", autospec=True) as mock_pg,
                patch.object(collector, "_check_redis_health", autospec=True) as mock_redis,
            ):
                mock_service.return_value = ContainerMetrics(
                    name="x", status="unknown", health="unhealthy"
                )
                mock_pg.return_value = ContainerMetrics(
                    name="postgres", status="unknown", health="unhealthy"
                )
                mock_redis.return_value = ContainerMetrics(
                    name="redis", status="unknown", health="unhealthy"
                )
                result = await collector.collect_container_health()
                names = [c.args[-2] for c in mock_service.call_args_list]
                urls = [c.args[-1] for c in mock_service.call_args_list]
                assert names == ["frontend", "ai-yolo26", "ai-llm"]  # kills case/None names
                assert urls == [
                    "http://frontend:8080/health",  # kills rstrip(None)/lstrip('/')
                    "http://ai-yolo26:8095/health",
                    "http://ai-llm:8091/health",
                ]
                for c in mock_service.call_args_list:  # client arg never None
                    assert all(a is not None for a in c.args[:-2])
            assert result[0].name == "backend"
            assert result[0].status == "running"  # kills XXrunningXX / RUNNING

    @pytest.mark.asyncio
    async def test_check_service_health_non_200_contract(self) -> None:
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock()
            collector = PerformanceCollector()
            mock_response = MagicMock()
            mock_response.status_code = 500
            with patch("httpx.AsyncClient.get", return_value=mock_response, autospec=True) as get_mock:
                client = httpx.AsyncClient()
                result = await collector._check_service_health(
                    client, "svc", "http://svc:1/health"
                )
                await client.aclose()
            # request target + timeout contract (kills url None / timeout None / 3.0 / removed)
            assert get_mock.call_args.args[1] == "http://svc:1/health"
            assert get_mock.call_args.kwargs.get("timeout") == 2.0
            # non-200 branch contract: service exists but unhealthy
            assert (result.name, result.status, result.health) == (
                "svc", "running", "unhealthy",
            )  # kills None/removed/case status+name+health mutants (C26)

    @pytest.mark.asyncio
    async def test_check_service_health_200_status_running(self) -> None:
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock()
            collector = PerformanceCollector()
            mock_response = MagicMock()
            mock_response.status_code = 200
            with patch("httpx.AsyncClient.get", return_value=mock_response, autospec=True):
                client = httpx.AsyncClient()
                result = await collector._check_service_health(
                    client, "svc", "http://svc:1/health"
                )
                await client.aclose()
            assert (result.name, result.status, result.health) == ("svc", "running", "healthy")

    @pytest.mark.asyncio
    async def test_postgres_health_uses_select_1_and_unknown_on_failure(self) -> None:
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock()
            with patch("backend.core.database.get_session_factory", autospec=True) as mock_factory:
                mock_session = AsyncMock()
                mock_session.__aenter__.return_value = mock_session
                mock_session.__aexit__.return_value = None
                mock_factory.return_value = lambda: mock_session
                collector = PerformanceCollector()
                result = await collector._check_postgres_health()
                query = mock_session.execute.call_args.args[0]
                assert str(query) == "SELECT 1"  # kills execute(None)/XXSELECT 1XX
            with patch("backend.core.database.get_session_factory", autospec=True) as mock_factory:
                mock_session = AsyncMock()
                mock_session.__aenter__.side_effect = Exception("DB down")
                mock_factory.return_value = lambda: mock_session
                result = await collector._check_postgres_health()
                assert (result.name, result.status, result.health) == (
                    "postgres", "unknown", "unhealthy",
                )  # kills XXunknownXX / UNKNOWN (C26b)

    @pytest.mark.asyncio
    async def test_redis_health_except_branch_unknown_status(self) -> None:
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock()
            with patch("backend.core.redis.init_redis", autospec=True) as mock_init:
                mock_init.side_effect = Exception("Redis down")
                collector = PerformanceCollector()
                result = await collector._check_redis_health()
                assert (result.name, result.status, result.health) == (
                    "redis", "unknown", "unhealthy",
                )  # kills XXunknownXX / UNKNOWN (C26b)


class TestMetricsFallbackContracts:
    """UNVERIFIED. Kills C22 (16 yolo26), C23 (9 nemotron), C27 (9 postgresql),
    C28/C29/C30 (26 redis)."""

    @pytest.mark.asyncio
    async def test_yolo26_url_and_defaults_contract(self) -> None:
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock(yolo26_url="http://ai-yolo26:8095")
            collector = PerformanceCollector()
            with patch.object(collector, "_get_http_client", autospec=True) as mock_get_client:
                mock_client = AsyncMock()
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"status": "healthy"}
                mock_client.get.return_value = mock_response
                mock_get_client.return_value = mock_client
                result = await collector.collect_yolo26_metrics()
                assert mock_client.get.call_args.args[0] == "http://ai-yolo26:8095/health"
                assert (result.model, result.device, result.vram_gb) == (
                    "yolo26", "unknown", 0,
                )  # kills None/removed/XX/YOLO26/UNKNOWN default mutants (C22)
                mock_client.get.side_effect = Exception("refused")
                result = await collector.collect_yolo26_metrics()
                assert (result.status, result.model, result.device, result.vram_gb) == (
                    "unreachable", "yolo26", "unknown", 0,
                )  # kills unreachable-literal case mutants

    @pytest.mark.asyncio
    async def test_nemotron_slot_semantics_contract(self) -> None:
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock(nemotron_url="http://ai-llm:8091")
            collector = PerformanceCollector()
            with patch.object(collector, "_get_http_client", autospec=True) as mock_get_client:
                mock_client = AsyncMock()
                mock_response = MagicMock()
                mock_response.status_code = 200
                # slot without state + distinct n_ctx values
                mock_response.json.return_value = [
                    {"n_ctx": 8192},
                    {"state": 0, "n_ctx": 4096},
                ]
                mock_client.get.return_value = mock_response
                mock_get_client.return_value = mock_client
                result = await collector.collect_nemotron_metrics()
                assert mock_client.get.call_args.args[0] == "http://ai-llm:8091/slots"
                assert result.slots_active == 0  # missing state == idle (kills 11/13/16)
                assert result.slots_total == 2
                assert result.context_size == 8192  # first slot (kills slots[1])
                mock_response.json.return_value = [{"state": 1}]
                result = await collector.collect_nemotron_metrics()
                assert result.context_size == 4096  # default (kills None/4097/removed)
                mock_client.get.side_effect = Exception("refused")
                result = await collector.collect_nemotron_metrics()
                assert (result.status, result.slots_active, result.slots_total,
                        result.context_size) == ("unreachable", 0, 0, 0)  # kills ctx=1

    @pytest.mark.asyncio
    async def test_postgresql_healthy_values_and_fallback_contract(self) -> None:
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock(
                database_pool_size=10, database_pool_overflow=20
            )
            with patch("backend.core.database.get_session_factory", autospec=True) as mock_factory:
                mock_session = AsyncMock()
                mock_session.__aenter__.return_value = mock_session
                mock_session.__aexit__.return_value = None

                mock_result = MagicMock()

                async def mock_execute(query):
                    q = str(query)
                    if "pg_stat_activity" in q:
                        assert q == "SELECT count(*) FROM pg_stat_activity WHERE state = 'active'"
                        mock_result.scalar.return_value = 7
                    elif "blks_hit" in q:
                        mock_result.scalar.return_value = 98.0
                    else:
                        mock_result.scalar.return_value = 100
                    return mock_result

                mock_session.execute = mock_execute
                mock_factory.return_value = lambda: mock_session
                collector = PerformanceCollector()
                result = await collector.collect_postgresql_metrics()
                assert result.status == "healthy"
                assert result.connections_active == 7  # kills scalar() or 1 (C27)
                assert result.cache_hit_ratio == 98.0  # kills or 101 (C27)
                assert result.transactions_per_min == 100.0  # kills or 1 / and 0 (C27)
                assert result.connections_max == 30
            # unreachable path: full literal (kills active=1; incidentally 31/1/1 - C11)
            with patch("backend.core.database.get_session_factory", autospec=True) as mock_factory:
                mock_factory.side_effect = Exception("boom")
                collector = PerformanceCollector()
                result = await collector.collect_postgresql_metrics()
                assert (result.status, result.connections_active,
                        result.connections_max, result.cache_hit_ratio,
                        result.transactions_per_min) == ("unreachable", 0, 30, 0.0, 0.0)

    @pytest.mark.asyncio
    async def test_redis_missing_info_keys_and_zero_input(self) -> None:
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock()
            with patch("backend.core.redis.init_redis", autospec=True) as mock_init:
                mock_raw = MagicMock()

                async def info_empty():
                    return {}

                mock_raw.info = info_empty
                mock_client = MagicMock()
                mock_client._ensure_connected.return_value = mock_raw
                mock_init.return_value = mock_client
                collector = PerformanceCollector()
                result = await collector.collect_redis_metrics()
                # payload with no keys must stay healthy with all-zero values:
                # kills default mutations (None/removed/1), get(None), and the
                # ZeroDivision-adjacent ratio guards (or True / >= 0 / else 1)
                assert (result.status, result.connected_clients, result.memory_mb,
                        result.hit_ratio, result.blocked_clients) == (
                    "healthy", 0, 0.0, 0.0, 0,
                )

    @pytest.mark.asyncio
    async def test_redis_real_info_values_and_single_hit(self) -> None:
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock()
            with patch("backend.core.redis.init_redis", autospec=True) as mock_init:
                mock_raw = MagicMock()

                async def info_full():
                    return {
                        "connected_clients": 5,
                        "used_memory": 2 * 1024 * 1024,
                        "keyspace_hits": 1,
                        "keyspace_misses": 0,
                        "blocked_clients": 7,
                    }

                mock_raw.info = info_full
                mock_client = MagicMock()
                mock_client._ensure_connected.return_value = mock_raw
                mock_init.return_value = mock_client
                collector = PerformanceCollector()
                result = await collector.collect_redis_metrics()
                assert result.connected_clients == 5
                assert result.memory_mb == 2.0
                assert result.hit_ratio == 100.0  # 1 hit / 1 total (kills hits-misses, >1)
                assert result.blocked_clients == 7  # pins info key names (C28 key mutants)

    @pytest.mark.asyncio
    async def test_redis_unreachable_full_zero_contract(self) -> None:
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock()
            with patch("backend.core.redis.init_redis", autospec=True) as mock_init:
                mock_client = MagicMock()
                mock_client._ensure_connected.side_effect = RuntimeError("down")
                mock_init.return_value = mock_client
                collector = PerformanceCollector()
                result = await collector.collect_redis_metrics()
                assert (result.status, result.connected_clients, result.memory_mb,
                        result.hit_ratio, result.blocked_clients) == (
                    "unreachable", 0, 0, 0, 0,
                )  # kills the +1 filler mutants (C30)


class TestThroughputAndInferenceContract:
    """UNVERIFIED. Kills C31 (20 throughput-helper), C32 (21 tracker call-arg),
    C33 (6 seeds/session), C34 (42 latency dict), C35 (6 queues)."""

    @pytest.mark.asyncio
    async def test_detections_cutoff_window_tz_and_rounding(self) -> None:
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock()
            collector = PerformanceCollector()
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar.return_value = 151  # 30.2 - not an integer fifth
            mock_session.execute.return_value = mock_result
            result = await collector._get_detections_per_minute(mock_session)
            assert result == 30.2  # kills round(..., None) / round(...) -> int
            stmt = mock_session.execute.call_args.args[0]
            sql = str(stmt)
            assert "count(detections.id)" in sql  # kills select(None)/count(None)
            wc = stmt.whereclause
            assert wc is not None and "detected_at" in str(wc)  # kills where(None)/drop
            assert wc.operator is operator.ge  # kills >= -> >
            bound = wc.right.value
            assert bound.utcoffset() == timedelta(0)  # kills datetime.now(None)
            window = (datetime.now(UTC) - bound) - timedelta(minutes=5)
            assert abs(window.total_seconds()) <= 5  # kills +timedelta / minutes=6

    @pytest.mark.asyncio
    async def test_events_cutoff_window_tz_and_rounding(self) -> None:
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock()
            collector = PerformanceCollector()
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar.return_value = 26  # 5.2
            mock_session.execute.return_value = mock_result
            result = await collector._get_events_per_minute(mock_session)
            assert result == 5.2
            stmt = mock_session.execute.call_args.args[0]
            assert "count(event.id)" in str(stmt)
            wc = stmt.whereclause
            assert wc.operator is operator.ge and "started_at" in str(wc)
            bound = wc.right.value
            assert bound.utcoffset() == timedelta(0)
            window = (datetime.now(UTC) - bound) - timedelta(minutes=5)
            assert abs(window.total_seconds()) <= 5

    @pytest.mark.asyncio
    async def test_inference_metrics_tracker_and_output_contract(self) -> None:
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock()
            with patch(
                "backend.core.metrics.get_pipeline_latency_tracker", autospec=True
            ) as mock_tracker:
                tracker = MagicMock()

                def stage_stats(stage, window_minutes=None):
                    assert stage in {"watch_to_detect", "batch_to_analyze", "total_pipeline"}
                    assert window_minutes == 5
                    return {"avg_ms": 100.0, "p95_ms": 200.0, "p99_ms": 250.0}

                tracker.get_stage_stats.side_effect = stage_stats
                mock_tracker.return_value = tracker
                mock_session = AsyncMock()
                mock_session.__aenter__.return_value = mock_session
                mock_session.__aexit__.return_value = None
                with patch(
                    "backend.core.database.get_session",
                    return_value=mock_session, autospec=True,
                ):
                    collector = PerformanceCollector()

                    async def dpm(session):
                        return 30.2

                    async def epm(session):
                        return 5.2

                    with (
                        patch.object(collector, "_get_detections_per_minute",
                                     side_effect=dpm, autospec=True) as md,
                        patch.object(collector, "_get_events_per_minute",
                                     side_effect=epm, autospec=True) as me,
                    ):
                        result = await collector.collect_inference_metrics()
                    assert result is not None
                    # real session handed to the helpers (kills session->None, C33)
                    assert md.call_args.args[-1] is mock_session
                    assert me.call_args.args[-1] is mock_session
                    # full latency contract (kills C32/C34)
                    assert result.yolo26_latency_ms == {"avg": 100.0, "p95": 200.0, "p99": 250.0}
                    assert result.nemotron_latency_ms == {"avg": 100.0, "p95": 200.0, "p99": 250.0}
                    assert result.pipeline_latency_ms == {"avg": 100.0, "p95": 200.0}
                    assert result.throughput == {"images_per_min": 30.2, "events_per_min": 5.2}
                    assert result.queues == {"detection": 0, "analysis": 0}  # kills C35

    @pytest.mark.asyncio
    async def test_inference_missing_stats_and_db_failure(self) -> None:
        with patch(
            "backend.services.performance_collector.get_settings", autospec=True
        ) as mock_settings:
            mock_settings.return_value = MagicMock()
            with patch(
                "backend.core.metrics.get_pipeline_latency_tracker", autospec=True
            ) as mock_tracker:
                tracker = MagicMock()
                tracker.get_stage_stats.return_value = {}  # no stats at all
                mock_tracker.return_value = tracker
                with patch(
                    "backend.core.database.get_session", autospec=True,
                    side_effect=Exception("db down"),
                ):
                    collector = PerformanceCollector()
                    result = await collector.collect_inference_metrics()
                    assert result is not None  # seed mutants -> None -> kills C33
                    # `or 0` fallbacks must be 0, never 1 (kills C34 or-1 mutants)
                    assert result.yolo26_latency_ms == {"avg": 0, "p95": 0, "p99": 0}
                    assert result.nemotron_latency_ms == {"avg": 0, "p95": 0, "p99": 0}
                    assert result.pipeline_latency_ms == {"avg": 0, "p95": 0}
                    assert result.throughput == {"images_per_min": 0.0, "events_per_min": 0.0}
```

## Verification procedure (for the serial pytest lane, not this wave)

1. `uv run pytest backend/tests/unit/services/test_performance_collector.py -q` — the 6 drafted
   classes must be GREEN against the current (original) module.
2. For each drafted class, re-run `mutmut run --paths-to-mutate` scoped to the module (or apply
   the one-line diffs individually via the copy's variant bodies) — every cluster listed as
   killed must flip from survived to killed.
3. Clusters deliberately NOT killed (EQUIVALENT: C01-C05, C06a, C07, C08, C10, C15a;
   LOW-VALUE: C11 — incidentally killed by the pg unreachable assert; consider `mutmut` config
   `skip` for the logger cluster if the baseline wants a clean score).
