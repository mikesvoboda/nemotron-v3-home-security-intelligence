# WP4.4 Triage Dossier — backend/services/detector_registry.py

Source: `mutants/backend/services/detector_registry.py.meta` — 188 mutants, all checked.
**Survivors (exit_code 0): 89.** Diffs via in-process `mutmut.__main__.get_diff_for_mutant` (all 89 succeeded; raw diffs in `/tmp/wp25/wp44-triage/dr-shows/`).

Covering test files (from `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`):

- `backend/tests/unit/services/test_detector_registry.py`
  - register/set_active/list: `TestDetectorRegistry` L55-192 (register 58-92, set_active 101-136, get_active_config 138-158, list 160-192)
  - check_health: `TestDetectorRegistryHealth` L194-277 (healthy 198, unhealthy 223, all 246)
  - singleton/init: `TestDetectorRegistrySingleton` L279-297
  - switch: `TestDetectorRegistrySwitching` L300-393 (force test L369-393)
- `backend/tests/unit/api/routes/test_detector_routes.py`
  - fixture `mock_registry` L29-66 (calls `reset_detector_registry()` L32 but never re-reads the singleton)
  - list routes L103-169 (assert only key *presence*, L140-148: `detector_type/display_name/enabled/is_active/url` — no value checks for model_version/description/url)
  - health route L356-403 (registry is mocked → registry `check_health` internals not exercised)

Key structural facts driving classifications:

- **No test captures log output anywhere** (`grep caplog` = zero hits in both files). Every mutant that only changes `logger.info/warning` message text or `extra=` dict keys is unkillable without log assertions → EQUIVALENT per convention.
- Health tests fully mock `httpx.AsyncClient` (autospec) — mock accepts any URL/any timeout, so URL/timeout changes pass silently.
- `switch_detector` service tests discard the returned `status`; the route builds its response from `get_active_config()` + only `status.healthy`, and the route force-test asserts only `status_code == 200` — so force-placeholder status fields are invisible at every layer.
- Singleton tests assert only `"yolo26" in registry.available_detectors` (L297) — zero field-value assertions on default configs.
- Route health test L356-386 goes through a MOCKED registry (`latency_ms=15.5` is fixture-supplied), so registry-side latency computation is asserted nowhere.

## Cluster table (counts sum to 89)

| # | Pattern (function / concern) | Count | Keys (≤3 examples) | Class | Why |
|---|---|---|---|---|---|
| 1 | `register()` logger.info mutations: msg→None (2), extra→None (3), extra-param dropped (5), extra keys `XX…XX`/`UPPER` renames (6,7,8,9,10,11) | 9 | `…ǁregister__mutmut_2`, `_3`, `_6` | EQUIVALENT | Pure log text/extra-key churn; `_detectors[config.detector_type] = config` untouched; no log assertions exist |
| 2 | `set_active()` logger.info mutations: msg→None (7), extra→None (8), extra dropped (10), key renames (11,12) | 5 | `…ǁset_active__mutmut_7`, `_8`, `_11` | EQUIVALENT | Same — state assignment survives |
| 3 | `check_health()` exception-path `logger.warning` mutations: msg→None (36), extra→None (37), extra dropped (39), key renames (40-43), extra error value `str(None)` (44) | 8 | `…check_health__mutmut_36`, `_40`, `_44` | EQUIVALENT | Returned `error_message=str(e)` is a separate expression (test L244 still passes); only the log payload changes |
| 4 | `switch_detector()` success-log mutations: `old_active=None` (21, feeds only log/extra), msg→None (23), extra→None (24), extra dropped (26), key renames (27-32) | 10 | `…switch_detector__mutmut_21`, `_23`, `_27` | EQUIVALENT | `_active_detector` assignment and return path untouched |
| 5 | `_initialize_default_detectors()` final `logger.info` mutations: msg→None (37), extra→None (38), extra dropped (40), msg case tweaks (41,42,43), extra key renames (44-47) | 10 | `…initialize_default_detectors__mutmut_37`, `_41`, `_44` | EQUIVALENT | Registration + `set_active("yolo26")` run before the log; test L297 passes |
| 6 | `_initialize_default_detectors()` drops `enabled=True` kwarg from yolo26 `DetectorConfig` (12) | 1 | `…initialize_default_detectors__mutmut_12` | EQUIVALENT | `DetectorConfig.enabled` dataclass default IS `True` (L63) → byte-identical semantics |
| 7 | `get_active_config()` raise message wrapped: `"No active detector configured"` → `"XX…XX"` (3) | 1 | `…get_active_config__mutmut_3` | LOW-VALUE | Real string change surfaced as API error detail, but test L157 `match="No active detector"` still matches the XX-wrapped text; nobody should assert exact error prose |
| 8 | `list_detectors()` field-loss in `DetectorInfo`: `model_version=None` (8), drop `model_version=` kwarg → default None (15), drop `description=` kwarg → default "" (16) | 3 | `…list_detectors__mutmut_8`, `_15`, `_16` | TEST-GAP | Service test L184-191 asserts display_name/enabled/is_active only; route test asserts key presence only (and not even model_version/description keys) — config→info value flow for model_version/description never asserted |
| 9 | `check_health()` SUCCESS-path latency_ms loss: `latency_ms=None` (9), status kwarg None (19) / dropped (23) | 6 | `…check_health__mutmut_9`, `_19`, `_23` | TEST-GAP | Healthy test L219-221 asserts detector_type/healthy/model_loaded — latency never; route latency assertion uses a mocked registry |
| 10 | `check_health()` SUCCESS-path latency arithmetic scale/sign: `*1000→/1000` (10), `-→+` (11), `*1001` (12) | 3 | `…check_health__mutmut_10`, `_11`, `_12` | TEST-GAP | Same — ms value never asserted; /1000 and +/*1001 only killable by pinning `time.monotonic` |
| 11 | `check_health()` EXCEPTION-path latency loss: `latency_ms=None` (32), status None (47) / kwarg dropped (51) | 4 | `…check_health__mutmut_32`, `_47`, `_51` | TEST-GAP | Unhealthy test L242-244 asserts healthy/error_message only |
| 12 | `check_health()` EXCEPTION-path latency arithmetic: `/1000` (33), `+` (34), `*1001` (35) | 3 | `…check_health__mutmut_33`, `_34`, `_35` | TEST-GAP | Same as #10 on the except branch |
| 13 | `check_health()` health endpoint URL → None: `health_url = f"{config.url}/health"` → `None` (3), `client.get(health_url)` → `client.get(None)` (8) | 2 | `…check_health__mutmut_3`, `_8` | TEST-GAP | PRODUCTION-BREAKING: real httpx `.get(None)` raises → every health check reports unhealthy; mocked AsyncMock swallows `get(None)` and tests pass. Requested URL never asserted |
| 14 | `check_health()` httpx client timeout: `5.0→None` (5), `5.0→6.0` (6) | 2 | `…check_health__mutmut_5`, `_6` | TEST-GAP | `None` = unbounded hang on a hung detector service; autospec mock records the kwarg but no test asserts it (`assert_called_once_with(timeout=5.0)` is a one-liner away) |
| 15 | `check_health()` `model_loaded=data.get("model_loaded", False)` default mutated → None (26), → missing default/None (28), → True (31) | 3 | `…check_health__mutmut_26`, `_28`, `_31` | TEST-GAP | Observable only when health JSON lacks `model_loaded` (realistic); every mock payload includes the key (L214), so fallback path never executed/asserted |
| 16 | `switch_detector()` force-path placeholder `DetectorStatus` fields: `detector_type=None` (13), `model_loaded=True→None` (15) / kwarg dropped→False (18), `healthy=True→False` (19) | 5 | `…switch_detector__mutmut_13`, `_15`, `_19` | TEST-GAP | Force test L389-393 discards return value; route response `healthy=status.healthy` unasserted (route force test checks only status 200) → a force switch can report `healthy=False`/`detector_type=None` silently |
| 17 | `_initialize_default_detectors()` yolo26 `DetectorConfig` field values: →None (4,5,7,8), kwargs dropped (13: model_version→None, 14: description→generic default), string case/XX tweaks (17,18,20,21,22,23,24) | 13 | `…initialize_default_detectors__mutmut_4`, `_5`, `_7` | TEST-GAP | Biggest single-test kill: singleton test asserts only membership (L297); `registry.get_config("yolo26")` field values (url from settings, "yolo26m", display name, description) asserted nowhere |
| 18 | `_initialize_default_detectors()` yolov8 lookup neutered: `yolov8_url=None` (26), `getattr(None,…)` (27), attr name `"XXyolov8_urlXX"` (32), `"YOLOV8_URL"` (33) | 4 | `…initialize_default_detectors__mutmut_26`, `_27`, `_32` | TEST-GAP | Real change: YOLOv8 silently unregistered even when `settings.yolov8_url` is configured. Tests run with default settings (no yolov8_url) so the branch never taken — no test covers init with yolov8 configured |
| 19 | `reset_detector_registry()` `DetectorRegistry._instance = None` → `""` (1) | 1 | `…reset_detector_registry__mutmut_1` | TEST-GAP | `""` is falsy but not None → `get_detector_registry()` returns the **string `""`** as "registry". Routes tests call reset (fixture L32) but never re-read the singleton; singleton tests patch `_instance` directly. A poisoned global that breaks every real caller |

**Totals: TEST-GAP 45, EQUIVALENT 43, LOW-VALUE 1. Sum = 89.**

## Drafted kill-tests (highest-value TEST-GAP clusters)

Target file: `backend/tests/unit/services/test_detector_registry.py` (existing imports: `AsyncMock, MagicMock, patch`, `pytest`, module imports L13-18; **reset test additionally needs `reset_detector_registry` added to the L13-18 import** and `types.SimpleNamespace`).
TDD procedure (same for each): run the new test against the mutant copy of `detector_registry.py` → the new assertion FAILS; run against original source → PASSES.

// UNVERIFIED - not yet run red/green (constraint: no test execution this session)

### T1 — kills #13 health-URL + #14 timeout (bonus) — `test_check_health_requests_configured_health_url`

```python
class TestCheckHealthRequestContract:
    """Pins the actual HTTP request the health check makes (WP4.4 #13/#14)."""

    @pytest.mark.asyncio
    async def test_check_health_requests_configured_health_url(self):
        """Health check must GET {config.url}/health on a bounded-timeout client."""
        registry = DetectorRegistry()
        registry.register(
            DetectorConfig(
                detector_type="yolo26",
                display_name="YOLO26",
                url="http://localhost:8095",
            )
        )

        with patch("httpx.AsyncClient", autospec=True) as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "healthy", "model_loaded": True}
            mock_client.get.return_value = mock_response

            await registry.check_health("yolo26")

            mock_client.get.assert_called_once_with("http://localhost:8095/health")
            mock_client_class.assert_called_once_with(timeout=5.0)
```

Kills #13 (get(None) / health_url=None) and #14 (timeout None/6.0). On original: passes.

### T2 — kills #9 success-latency-loss — `test_check_health_reports_latency_in_milliseconds`

```python
    @pytest.mark.asyncio
    async def test_check_health_reports_latency_in_milliseconds(self):
        """latency_ms must be the measured seconds delta scaled by 1000."""
        registry = DetectorRegistry()
        registry.register(
            DetectorConfig(
                detector_type="yolo26",
                display_name="YOLO26",
                url="http://localhost:8095",
            )
        )

        with (
            # start_time=100.0, after-response=100.5 → (0.5) * 1000 = 500.0 ms
            patch("time.monotonic", side_effect=[100.0, 100.5]),
            patch("httpx.AsyncClient", autospec=True) as mock_client_class,
        ):
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "healthy", "model_loaded": True}
            mock_client.get.return_value = mock_response

            status = await registry.check_health("yolo26")

            assert status.latency_ms == pytest.approx(500.0)
```

Kills #9 (None/None-default) and #10 mutants 10 (`/1000` → 0.0005) and 11 (`+` → 200500). Mutant 12 (`*1001` → 500.5) also dies to `approx(500.0)` at default rel=1e-6.

### T3 — kills #11 + #12 exception-path latency — `test_check_health_reports_latency_on_failure`

```python
    @pytest.mark.asyncio
    async def test_check_health_reports_latency_on_failure(self):
        """Failed health checks must also report computed latency_ms."""
        registry = DetectorRegistry()
        registry.register(
            DetectorConfig(
                detector_type="yolo26",
                display_name="YOLO26",
                url="http://localhost:8095",
            )
        )

        with (
            patch("time.monotonic", side_effect=[100.0, 100.5]),
            patch("httpx.AsyncClient", autospec=True) as mock_client_class,
        ):
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = Exception("Connection refused")

            status = await registry.check_health("yolo26")

            assert status.healthy is False
            assert status.latency_ms == pytest.approx(500.0)
```

Kills #11 (32, 47, 51 — None paths) and #12 (33 `/1000`, 34 `+`, 35 `*1001`).

### T4 — kills #16 force-placeholder fields — `test_switch_detector_with_force_returns_full_status`

```python
    @pytest.mark.asyncio
    async def test_switch_detector_with_force_returns_full_status(self):
        """Force switch must return a placeholder status describing the new active detector."""
        registry = DetectorRegistry()
        registry.register(
            DetectorConfig(
                detector_type="yolo26",
                display_name="YOLO26",
                url="http://localhost:8095",
            )
        )
        registry.register(
            DetectorConfig(
                detector_type="yolov8",
                display_name="YOLOv8",
                url="http://localhost:8096",
            )
        )
        registry.set_active("yolo26")

        with patch.object(registry, "check_health", autospec=True) as mock_health:
            status = await registry.switch_detector("yolov8", force=True)

            mock_health.assert_not_called()
            assert registry.active_detector == "yolov8"
            assert status.detector_type == "yolov8"
            assert status.healthy is True
            assert status.model_loaded is True
```

Kills all 5 of #16 (13 → detector_type None; 19 → healthy False; 15 → model_loaded None; 18/20 → False). Extends the existing force test L369-393 without duplicating it.

### T5 — kills #17 default yolo26 config (13 mutants) — `test_registry_default_yolo26_config_fields`

```python
class TestDetectorRegistrySingleton:
    def test_registry_default_yolo26_config_fields(self):
        """Default registry must carry the full documented yolo26 configuration."""
        fake_settings = SimpleNamespace(yolo26_url="http://localhost:8095")

        with (
            patch.object(DetectorRegistry, "_instance", None),
            patch(
                "backend.services.detector_registry.get_settings",
                return_value=fake_settings,
            ),
        ):
            registry = get_detector_registry()

            config = registry.get_config("yolo26")
            assert config.detector_type == "yolo26"
            assert config.display_name == "YOLO26"
            assert config.url == "http://localhost:8095"
            assert config.enabled is True
            assert config.model_version == "yolo26m"
            assert (
                config.description
                == "YOLO26 TensorRT object detection model for real-time security monitoring"
            )
            assert registry.active_detector == "yolo26"
```

Kills all 13 of #17 (every field None/dropped/case-flip/XX-wrapped trips one equality). #6 (enabled kwarg removal) legitimately survives — default is True.

### T6 — kills #19 reset sentinel — `test_reset_detector_registry_clears_singleton`

```python
    def test_reset_detector_registry_clears_singleton(self):
        """reset_detector_registry must set the sentinel to None (not a falsy value)."""
        with patch.object(DetectorRegistry, "_instance", None):
            first = get_detector_registry()

        reset_detector_registry()

        assert DetectorRegistry._instance is None
        second = get_detector_registry()
        assert isinstance(second, DetectorRegistry)
        assert second is not first
        assert "yolo26" in second.available_detectors
```

Kills #19 (`_instance = ""` trips `assert … is None` and the isinstance guard — `""` is falsy-but-not-None so `get_detector_registry()` would hand callers a string).

### One-line kill sketches for the remaining TEST-GAP clusters (not fully drafted)

- **#8 list_detectors fields**: extend `test_list_detectors_returns_info` — register with `model_version="yolo26m"`, `description="YOLO26 TensorRT object detection model for real-time security monitoring"`; `assert yolo26_info.model_version == "yolo26m"; assert yolo26_info.description == …; assert yolo26_info.url == "http://localhost:8095"`. Kills 8/15/16.
- **#15 model_loaded default**: payload `{"status": "healthy"}` (no key); `assert status.model_loaded is False`. Kills 26/28/31.
- **#18 yolov8 branch**: `SimpleNamespace(yolo26_url=…, yolov8_url="http://localhost:8096")`; `assert "yolov8" in registry.available_detectors` + url/enabled/model_version=="yolov8n" checks + `active_detector == "yolo26"`. Kills 26/27/32/33.

## Notes

- EQUIVALENT clusters (#1-#6, 43 mutants) are log-text/extra-key/default-kwarg churn; killing them would require `caplog`/structlog-capture assertions, which the project conventionally does not write (zero caplog usage in either covering file). Recommend marking them equivalent-closed in the WP4.4 ledger rather than drafting tests.
- LOW-VALUE #7: error-message wording; test at L157 deliberately uses a substring match, so it survives by design.
- The `xǁ…ǁ` mangling in keys denotes `DetectorRegistry` methods; `x__initialize_default_detectors` / `x_reset_detector_registry` are module-level functions.
