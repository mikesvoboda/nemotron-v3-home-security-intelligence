# WP4.4 Triage Dossier — backend/api/routes/health_ai_services.py

**Survivors: 111 / 328 total mutants (217 killed, 0 unchecked).** Source: `mutants/backend/api/routes/health_ai_services.py.meta` (exit_code 0).
Diffs captured from `uv run mutmut show <key>` (all 111 OK, saved under `/tmp/wp25/wp44-triage/diffs/health_ai_services/`).

Covering test files (from `mutants/mutmut-stats.json` `tests_by_mangled_function_name`):

- `backend/tests/unit/api/routes/test_health_ai_services.py` (934 lines; classes at L102 CB-state, L152 CB-metrics, L191 error-rate, L236 service-health-check, L498 queue-depths, L617 overall-status, L715 endpoint, L908 config) — **primary**
- `backend/tests/unit/api/routes/test_health.py` (639 lines; imports the same module helpers at L20 — partially duplicate suite)

Key structural fact driving most clusters: `AIServiceHealthDetail` (backend/api/schemas/ai_services_health.py) defaults every optional field (`circuit_state=CLOSED`, `last_health_check=None`, `error_rate_1h=None`, `latency_p99_ms=None`, `url=None`, `error=None`). So a *removed* kwarg is behavior-changing unless it already equals the default.

## Cluster table

| # | Cluster | N | Class | Example keys (x__check_ai_service_health unless noted) | Evidence |
|---|---------|---|-------|--------------------------------------------------------|----------|
| G1 | `_calculate_error_rate`: missing-key fallback `metrics.get("failure_count"/"rejected_calls", 0)` → None/1/empty-default (L161-162) | 6 | TEST-GAP | calculate_error_rate__13, __15, __18 (also 21,23,26) | All tests pass complete metrics dicts; `test_calculate_error_rate_missing_fields` only exercises `{}` (early-returns via total_calls). The "total_calls present, error fields absent → 0.0" path is never asserted; mutant raises TypeError there. test_health_ai_services.py:219 |
| G2 | `_get_circuit_breaker_metrics`: `status.get(key, 0)` → None/1/empty for failure_count/total_calls/rejected_calls (L137-139) | 9 | TEST-GAP | get_circuit_breaker_metrics__18, __27, __36 (all but _3) | Mocks always supply all 3 keys (test:161-165); missing-key contract (`{}` → all zeros) unasserted. test_health_ai_services.py:152 |
| G3 | `registry.get(service_name)` → `registry.get(None)` in `_get_circuit_breaker_state` (L101) + `_get_circuit_breaker_metrics` (L126) | 2 | TEST-GAP | get_circuit_breaker_state__3, get_circuit_breaker_metrics__3 | Tests mock `registry.get` with `return_value` (ignores args); never assert the lookup key. Wrong-key lookup invisible. test_health_ai_services.py:105-149,155 |
| G4 | `_calculate_overall_status`: `cfg.get("critical", False)` → truthy default (L351) — any config entry *missing* `critical` silently becomes critical | 3 | TEST-GAP | calculate_overall_status__10 (default True; muts 5/7 use falsy None = input-equivalent) | No test runs `_calculate_overall_status` with a config lacking the `critical` key; `test_config_has_all_required_fields` asserts the key exists but that's the config, not the function. |
| G5 | `_check_ai_service_health` preamble clobbers (L183-190): `name=None`, `circuit_breaker_name` lookup key/default mutations, `service_config.get(name)`, `getattr(settings, url_attr, )`, `_get_circuit_breaker_state/metrics(None)`, `error_rate=None` | 12 | TEST-GAP | check__1, check__7, check__21 (all of 1,7,8,9,10,11,12,13,19,21,23,24) | Registry mocked with `return_value` regardless of key → the breaker-name wiring (config key `circuit_breaker_name` → registry lookup) is executed but never asserted. If it breaks, services report CLOSED/default metrics and no test notices. |
| G6 | Return kwargs: `circuit_state=circuit_state,` removed → falls back to CLOSED (L196,235,245,255,266: url-not-configured, HTTP-non200, connect-error, timeout, generic-exc branches) | 5 | TEST-GAP | check__33, check__98, check__117, check__134, check__149 | Tests assert circuit_state only in HEALTHY/HALF_OPEN/OPEN-short-circuit branches (test:277,306,490); every UNHEALTHY/UNKNOWN branch drops the assertion. A non200/connect/timeout/generic response always reports CLOSED, silently hiding OPEN/half-OPEN. |
| G7 | Return kwargs: `url=service_url,` removed **or** set to None → url lost from response (L212,230,239,249,259,270) | 12 | TEST-GAP | check__55, check__48, check__102 (removals 55,82,102,121,138,153; =None 48,76,95,114,131,146) | Only the UNKNOWN branch asserts `result.url is None` (test:254); no test asserts the configured URL is echoed back in any health response. |
| G8 | Return kwargs: `last_health_check` removed → None, or explicitly None (L197…267, all 7 branches; mutants `=None` and removal) | 14 | TEST-GAP | check__34, check__79, check__118 (all of 29,34,46,52,73,79,92,99,112,118,129,135,144,150) | No test anywhere asserts `last_health_check` is populated; the field is dead in the test suite. Health monitoring that never timestamps checks is indistinguishable from working. |
| G9 | Return kwargs: `error_rate_1h` removed/None (L198…268, all 7 branches) | 14 | TEST-GAP | check__30, check__35, check__100 (all of 30,35,47,53,74,80,93,100,113,119,130,136,145,151) | Metrics fixtures deliberately load `get_status` with failure/rejected counts, but no assertion follows on the computed `error_rate_1h` — not even in the circuit-open test that uses {10 fails/100 calls/5 rejected} = 0.15. |
| G10 | Latency value fidelity (L221 arithmetic `*1000`→`/1000`,`+`,`*1001`; L229/L238 `round(latency_ms, 2)` → int-round/const-2/ndigits-3; L238 removal/None in HTTP branches) | 13 | TEST-GAP | check__66, check__87, check__94 (all of 66,67,68,86,87,88,89,94,101,106,107,108,109) | `test_healthy_service` (test:308) only asserts `latency_p99_ms is not None`. Wrong-unit math, constant latency, lost latency on non-200 — all invisible. |
| G11 | Success path `QueueDepthInfo(depth=safe_int(detection_depth), dlq_depth=detection_dlq_depth)` → `dlq_depth=` kwarg dropped → response detection DLQ always 0 (L320) | 1 | TEST-GAP | get_queue_depths__58 | `test_get_queue_depths_success` (test:502-512) uses side_effect [5,2,0,1] — detection_dlq happens to be 0; `test_get_queue_depths_updates_dlq_metrics` has detection_dlq=3 but only asserts the Prometheus call, not the returned response. The NEM-3891 fix (DLQ visibility) is unasserted on the response side. |
| L1 | `datetime.now(UTC)` → `datetime.now(None)` → naive timestamp (all 7 return branches) | 7 | LOW-VALUE | check__39, check__84, check__140 (all of 39,57,84,104,123,140,155) | Real change (aware→naive), but Pydantic accepts naive and the field is never asserted at all (see G8). Nobody should write a tz test for the mutant's sake; fold any tz assertion into G8's test naturally. |
| L2 | Circuit-open `error` message wrapped `"XX…XX"` (L213) | 1 | LOW-VALUE | check__58 | Test asserts `"Circuit breaker is open" in result.error` (substring survives the wrapping); message text cosmetic. |
| E1 | Removed return kwargs already equal the schema default: `latency_p99_ms=None` removal (L199,208,248,258,269), `url=None` removal in UNKNOWN branch (L200), `error=None` removal on success (L231) | 7 | EQUIVALENT | check__36, check__120, check__83 (all of 36,54,120,137,152,37,83) | Pydantic default == removed value → byte-identical model. |
| E2 | Redis-None early-return `QueueDepthInfo(depth=0, dlq_depth=0)` → `dlq_depth=` dropped → default 0 (L288-289) | 2 | EQUIVALENT | get_queue_depths__7, __15 | Default is 0. |
| E3 | `safe_int`: `int(val) if val is not None else 0` → `if (val is not None) or True` (L308) | 1 | EQUIVALENT | get_queue_depths__37 | The `isinstance(val, Exception)` branch returns first; None never reaches the mutated guard. |
| E4 | `logger.warning(f"…")` → `logger.warning(None)` (health-check generic-exception L263, queue safe_int L306) | 2 | EQUIVALENT | check__141, get_queue_depths__34 | Pure log text; no data flow. |

**Totals: TEST-GAP 91, LOW-VALUE 8, EQUIVALENT 12 → 111.**

## Why so many survivors concentrate in `_check_ai_service_health` return statements

The existing suite asserts `status` and `error` on each branch but leaves `last_health_check`, `error_rate_1h`, `url`, `circuit_state` (unhealthy branches) unasserted — 3-4 free kwargs per return × 7 branches. The field-completeness tests (T1/T2/T3 below) kill 53 of the 91 TEST-GAP survivors (G6∪G7∪G8∪G9∪G10 = 58 minus the 5 default-equal removals already classed EQUIVALENT).

## Drafted tests — UNVERIFIED - not yet run red/green

Style follows `backend/tests/unit/api/routes/test_health_ai_services.py` (class-based, `unittest.mock.patch` autospec, `@pytest.mark.asyncio`, helper `create_mock_settings`). Append to that file after `TestAIServiceHealthCheck`. TDD: run each against the mutant diff — the named assert must FAIL (red); run against original source — must PASS (green).

```python
# UNVERIFIED - not yet run red/green. Kills clusters G7 (url), G8 (last_health_check),
# G9 (error_rate_1h): every non-short-circuit branch must echo the configured URL,
# carry a health-check timestamp, and carry the CB-derived error rate.
class TestHealthDetailFieldCompleteness:
    """All response branches must populate url / last_health_check / error_rate_1h."""

    @pytest.mark.asyncio
    async def test_http_error_branch_carries_url_timestamp_and_error_rate(self) -> None:
        config = AI_SERVICES_CONFIG[0]  # yolo26
        settings = create_mock_settings()
        with patch("backend.services.circuit_breaker._get_registry", autospec=True) as mock_registry:
            mock_breaker = MagicMock()
            mock_breaker.state.value = "closed"
            mock_breaker.get_status.return_value = {
                "failure_count": 10, "total_calls": 100, "rejected_calls": 5,
            }
            mock_registry.return_value.get.return_value = mock_breaker

            with patch("httpx.AsyncClient.get", autospec=True) as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 500
                mock_get.return_value = mock_response

                result = await _check_ai_service_health(config, settings)

                assert result.status == AIServiceStatus.UNHEALTHY
                # G7: url echoed (kills check__102 removal and check__95 =None)
                assert result.url == "http://ai-yolo26:8095"
                # G8: timestamp populated (kills check__99 removal, check__92 =None)
                assert result.last_health_check is not None
                # G9: (10 + 5) / 100 -> 0.15 (kills check__100 removal, check__93 =None)
                assert result.error_rate_1h == 0.15

    @pytest.mark.asyncio
    async def test_circuit_open_branch_carries_url_timestamp_and_error_rate(self) -> None:
        config = AI_SERVICES_CONFIG[0]
        settings = create_mock_settings()
        with patch("backend.services.circuit_breaker._get_registry", autospec=True) as mock_registry:
            mock_breaker = MagicMock()
            mock_breaker.state.value = "open"
            mock_breaker.get_status.return_value = {
                "failure_count": 10, "total_calls": 100, "rejected_calls": 5,
            }
            mock_registry.return_value.get.return_value = mock_breaker

            result = await _check_ai_service_health(config, settings)

            assert result.status == AIServiceStatus.UNHEALTHY
            assert result.url == "http://ai-yolo26:8095"          # kills check__55, check__48
            assert result.last_health_check is not None            # kills check__52, check__46
            assert result.error_rate_1h == 0.15                    # kills check__53, check__47

    @pytest.mark.asyncio
    async def test_connect_error_branch_carries_url_timestamp_and_error_rate(self) -> None:
        config = AI_SERVICES_CONFIG[0]
        settings = create_mock_settings()
        with patch("backend.services.circuit_breaker._get_registry", autospec=True) as mock_registry:
            mock_breaker = MagicMock()
            mock_breaker.state.value = "closed"
            mock_breaker.get_status.return_value = {
                "failure_count": 3, "total_calls": 10, "rejected_calls": 2,
            }
            mock_registry.return_value.get.return_value = mock_breaker

            with patch("httpx.AsyncClient.get", autospec=True) as mock_get:
                mock_get.side_effect = httpx.ConnectError("Connection refused")

                result = await _check_ai_service_health(config, settings)

                assert result.status == AIServiceStatus.UNHEALTHY
                assert result.url == "http://ai-yolo26:8095"          # kills check__121, check__114
                assert result.last_health_check is not None            # kills check__118, check__112
                assert result.error_rate_1h == 0.5                     # kills check__119, check__113

    @pytest.mark.asyncio
    async def test_timeout_branch_carries_url_timestamp_and_error_rate(self) -> None:
        config = AI_SERVICES_CONFIG[0]
        settings = create_mock_settings()
        with patch("backend.services.circuit_breaker._get_registry", autospec=True) as mock_registry:
            mock_breaker = MagicMock()
            mock_breaker.state.value = "closed"
            mock_breaker.get_status.return_value = {
                "failure_count": 1, "total_calls": 4, "rejected_calls": 0,
            }
            mock_registry.return_value.get.return_value = mock_breaker

            with patch("httpx.AsyncClient.get", autospec=True) as mock_get:
                mock_get.side_effect = httpx.TimeoutException("slow")

                result = await _check_ai_service_health(config, settings)

                assert result.status == AIServiceStatus.UNHEALTHY
                assert result.url == "http://ai-yolo26:8095"          # kills check__138, check__131
                assert result.last_health_check is not None            # kills check__135, check__129
                assert result.error_rate_1h == 0.25                    # kills check__136, check__130

    @pytest.mark.asyncio
    async def test_generic_exception_branch_carries_url_timestamp_and_error_rate(self) -> None:
        config = AI_SERVICES_CONFIG[0]
        settings = create_mock_settings()
        with patch("backend.services.circuit_breaker._get_registry", autospec=True) as mock_registry:
            mock_breaker = MagicMock()
            mock_breaker.state.value = "closed"
            mock_breaker.get_status.return_value = {
                "failure_count": 7, "total_calls": 20, "rejected_calls": 3,
            }
            mock_registry.return_value.get.return_value = mock_breaker

            with patch("httpx.AsyncClient.get", autospec=True) as mock_get:
                mock_get.side_effect = ValueError("boom")

                result = await _check_ai_service_health(config, settings)

                assert result.status == AIServiceStatus.UNHEALTHY
                assert result.url == "http://ai-yolo26:8095"          # kills check__153, check__146
                assert result.last_health_check is not None            # kills check__150, check__144
                assert result.error_rate_1h == 0.5                     # (7+3)/20, kills check__151, check__145

    @pytest.mark.asyncio
    async def test_healthy_branch_echoes_configured_url(self) -> None:
        config = AI_SERVICES_CONFIG[0]
        settings = create_mock_settings()
        with patch("backend.services.circuit_breaker._get_registry", autospec=True) as mock_registry:
            mock_breaker = MagicMock()
            mock_breaker.state.value = "closed"
            mock_breaker.get_status.return_value = {
                "failure_count": 0, "total_calls": 10, "rejected_calls": 0,
            }
            mock_registry.return_value.get.return_value = mock_breaker

            with patch("httpx.AsyncClient.get", autospec=True) as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_get.return_value = mock_response

                result = await _check_ai_service_health(config, settings)

                assert result.status == AIServiceStatus.HEALTHY
                assert result.url == "http://ai-yolo26:8095"          # kills check__82, check__76
                assert result.last_health_check is not None            # kills check__79, check__73
                assert result.error_rate_1h == 0.0                     # kills check__80, check__74

    @pytest.mark.asyncio
    async def test_url_not_configured_branch_keeps_timestamp_and_error_rate(self) -> None:
        config = AI_SERVICES_CONFIG[0]
        settings = create_mock_settings(yolo26_url="")
        with patch("backend.services.circuit_breaker._get_registry", autospec=True) as mock_registry:
            mock_breaker = MagicMock()
            mock_breaker.state.value = "closed"
            mock_breaker.get_status.return_value = {
                "failure_count": 2, "total_calls": 8, "rejected_calls": 0,
            }
            mock_registry.return_value.get.return_value = mock_breaker

            result = await _check_ai_service_health(config, settings)

            assert result.status == AIServiceStatus.UNKNOWN
            assert result.last_health_check is not None                # kills check__34, check__29
            assert result.error_rate_1h == 0.25                        # kills check__35, check__30


# UNVERIFIED - not yet run red/green. Kills G6 (circuit_state removed -> CLOSED)
# on every branch that currently asserts no circuit state.
class TestCircuitStatePropagation:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "exc_or_status, expect_error",
        [(503, "HTTP 503"), (httpx.ConnectError("refused"), "Connection refused"),
         (httpx.TimeoutException("t"), "Timeout")],
    )
    async def test_half_open_breaker_survives_into_failure_responses(self, exc_or_status, expect_error) -> None:
        config = AI_SERVICES_CONFIG[0]
        settings = create_mock_settings()
        with patch("backend.services.circuit_breaker._get_registry", autospec=True) as mock_registry:
            mock_breaker = MagicMock()
            mock_breaker.state.value = "half_open"
            mock_breaker.get_status.return_value = {
                "failure_count": 1, "total_calls": 2, "rejected_calls": 0,
            }
            mock_registry.return_value.get.return_value = mock_breaker

            with patch("httpx.AsyncClient.get", autospec=True) as mock_get:
                if isinstance(exc_or_status, Exception):
                    mock_get.side_effect = exc_or_status
                else:
                    mock_response = MagicMock()
                    mock_response.status_code = exc_or_status
                    mock_get.return_value = mock_response

                result = await _check_ai_service_health(config, settings)

                assert expect_error in result.error
                # Original keeps HALF_OPEN; removed kwarg falls back to CLOSED -> red.
                assert result.circuit_state == AIServiceCircuitState.HALF_OPEN
                # kills check__98 (HTTP), check__117 (connect), check__134 (timeout)

    @pytest.mark.asyncio
    async def test_generic_exception_branch_keeps_half_open(self) -> None:
        config = AI_SERVICES_CONFIG[0]
        settings = create_mock_settings()
        with patch("backend.services.circuit_breaker._get_registry", autospec=True) as mock_registry:
            mock_breaker = MagicMock()
            mock_breaker.state.value = "half_open"
            mock_breaker.get_status.return_value = {
                "failure_count": 1, "total_calls": 2, "rejected_calls": 0,
            }
            mock_registry.return_value.get.return_value = mock_breaker

            with patch("httpx.AsyncClient.get", autospec=True) as mock_get:
                mock_get.side_effect = ValueError("boom")
                result = await _check_ai_service_health(config, settings)

            assert result.circuit_state == AIServiceCircuitState.HALF_OPEN  # kills check__149

    @pytest.mark.asyncio
    async def test_url_not_configured_keeps_open_circuit_state(self) -> None:
        config = AI_SERVICES_CONFIG[0]
        settings = create_mock_settings(yolo26_url="")
        with patch("backend.services.circuit_breaker._get_registry", autospec=True) as mock_registry:
            mock_breaker = MagicMock()
            mock_breaker.state.value = "open"
            mock_breaker.get_status.return_value = {
                "failure_count": 1, "total_calls": 2, "rejected_calls": 0,
            }
            mock_registry.return_value.get.return_value = mock_breaker

            result = await _check_ai_service_health(config, settings)

            assert result.status == AIServiceStatus.UNKNOWN
            assert result.circuit_state == AIServiceCircuitState.OPEN  # kills check__33


# UNVERIFIED - not yet run red/green. Kills G10 (latency value fidelity).
# Deterministic time.time(): latency_ms = 512.345 ms exactly.
class TestLatencyValueFidelity:
    @pytest.mark.asyncio
    async def test_healthy_latency_rounded_to_two_decimals(self) -> None:
        config = AI_SERVICES_CONFIG[0]
        settings = create_mock_settings()
        with patch("backend.services.circuit_breaker._get_registry", autospec=True) as mock_registry:
            mock_registry.return_value.get.return_value = None

            with patch("httpx.AsyncClient.get", autospec=True) as mock_get, patch(
                "backend.api.routes.health_ai_services.time.time",
                side_effect=[1_000_000.000, 1_000_000.512345],
            ):
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_get.return_value = mock_response

                result = await _check_ai_service_health(config, settings)

                # 0.512345s * 1000 -> round(512.345, 2) == 512.35
                # /1000 -> 0.0, +start -> huge, *1001 -> 512.857: all != 512.35
                # round(latency_ms) (None/empty ndigits) -> 512, round(2) -> 2, ndigits=3 -> 512.345
                assert result.latency_p99_ms == 512.35
                # kills check__66, 67, 68 (arith), check__86, 87, 88, 89 (round)

    @pytest.mark.asyncio
    async def test_http_error_branch_reports_measured_latency(self) -> None:
        config = AI_SERVICES_CONFIG[0]
        settings = create_mock_settings()
        with patch("backend.services.circuit_breaker._get_registry", autospec=True) as mock_registry:
            mock_registry.return_value.get.return_value = None

            with patch("httpx.AsyncClient.get", autospec=True) as mock_get, patch(
                "backend.api.routes.health_ai_services.time.time",
                side_effect=[1_000_000.000, 1_000_000.512345],
            ):
                mock_response = MagicMock()
                mock_response.status_code = 500
                mock_get.return_value = mock_response

                result = await _check_ai_service_health(config, settings)

                assert result.latency_p99_ms == 512.35
                # kills check__94 (=None), check__101 (removal), check__106-109 (round)


# UNVERIFIED - not yet run red/green. Kills G1 + G2 (missing-key defensive defaults).
class TestCircuitBreakerDefensiveDefaults:
    def test_error_rate_zero_when_error_fields_missing(self) -> None:
        # Original: .get(...,0) -> (0+0)/100 = 0.0.
        # Mutant: None + None -> TypeError (13/15/21/23), or 1+1 -> 0.02 (18/26).
        assert _calculate_error_rate({"total_calls": 100}) == 0.0

    def test_metrics_zero_when_status_missing_keys(self) -> None:
        with patch(
            "backend.services.circuit_breaker._get_registry", autospec=True
        ) as mock_registry:
            mock_breaker = MagicMock()
            mock_breaker.get_status.return_value = {}
            mock_registry.return_value.get.return_value = mock_breaker

            metrics = _get_circuit_breaker_metrics("yolo26")

            assert metrics == {"failure_count": 0, "total_calls": 0, "rejected_calls": 0}
            # mutants: values become None (18/27/36), 1 (23/32/41), or None via empty default


# UNVERIFIED - not yet run red/green. Kills G3 (registry lookup key clobbered to None).
class TestCircuitBreakerLookupKey:
    def test_state_lookup_uses_service_name(self) -> None:
        with patch(
            "backend.services.circuit_breaker._get_registry", autospec=True
        ) as mock_registry:
            mock_breaker = MagicMock()
            mock_breaker.state.value = "open"
            mock_registry.return_value.get.side_effect = (
                lambda name: mock_breaker if name == "yolo26" else None
            )

            state = _get_circuit_breaker_state("yolo26")

            assert state == AIServiceCircuitState.OPEN
            # mutant registry.get(None) -> side_effect returns None -> CLOSED. Kills state__3

    def test_metrics_lookup_uses_service_name(self) -> None:
        with patch(
            "backend.services.circuit_breaker._get_registry", autospec=True
        ) as mock_registry:
            mock_breaker = MagicMock()
            mock_breaker.get_status.return_value = {
                "failure_count": 4, "total_calls": 10, "rejected_calls": 1,
            }
            mock_registry.return_value.get.side_effect = (
                lambda name: mock_breaker if name == "yolo26" else None
            )

            metrics = _get_circuit_breaker_metrics("yolo26")

            assert metrics["failure_count"] == 4
            # mutant get(None) -> all-zero default. Kills metrics__3


# UNVERIFIED - not yet run red/green. Kills G4 (critical default truthified).
class TestOverallStatusMissingCriticalFlag:
    def test_entry_without_critical_flag_treated_as_non_critical(self, monkeypatch) -> None:
        import backend.api.routes.health_ai_services as mod

        monkeypatch.setattr(
            mod,
            "AI_SERVICES_CONFIG",
            [{"name": "clip"}],  # no "critical" key at all
        )
        services = {"clip": AIServiceHealthDetail(status=AIServiceStatus.UNHEALTHY)}

        # Original cfg.get("critical", False) -> falsy -> DEGRADED.
        # Mutant default True -> CRITICAL. Kills calculate_overall_status__10.
        # (Muts 5/7 default None are falsy -> equivalent on this input.)
        assert mod._calculate_overall_status(services) == AIServiceOverallStatus.DEGRADED


# UNVERIFIED - not yet run red/green. Kills G11 (response DLQ depth dropped)
# and G5 (preamble breaker-name wiring), the two singleton/small clusters.
class TestResponseDlqDepthAndBreakerWiring:
    @pytest.mark.asyncio
    async def test_detection_dlq_depth_flows_into_response(self) -> None:
        mock_redis = AsyncMock()
        # detection=10, analysis=5, detection_dlq=3, analysis_dlq=2
        mock_redis.get_queue_length.side_effect = [10, 5, 3, 2]

        result = await _get_queue_depths(mock_redis)

        assert result["detection_queue"].depth == 10
        # Original forwards detection_dlq_depth=3; mutant drops kwarg -> default 0.
        # Kills get_queue_depths__58.
        assert result["detection_queue"].dlq_depth == 3
        assert result["analysis_queue"].dlq_depth == 2

    @pytest.mark.asyncio
    async def test_health_check_resolves_breaker_by_configured_name(self) -> None:
        config = AI_SERVICES_CONFIG[0]  # yolo26, circuit_breaker_name="yolo26"
        settings = create_mock_settings()
        seen: list[str | None] = []

        with patch(
            "backend.services.circuit_breaker._get_registry", autospec=True
        ) as mock_registry:
            mock_breaker = MagicMock()
            mock_breaker.state.value = "open"
            mock_breaker.get_status.return_value = {
                "failure_count": 9, "total_calls": 9, "rejected_calls": 0,
            }

            def fake_get(name: str | None):
                seen.append(name)
                return mock_breaker if name == "yolo26" else None

            mock_registry.return_value.get.side_effect = fake_get

            result = await _check_ai_service_health(config, settings)

            # G5: preamble mutants pass None / mangled key -> registry misses the breaker
            # -> CLOSED -> HTTP path -> status HEALTHY not UNHEALTHY-open-short-circuit,
            # and seen would contain None. Kills check__1,7,8,9,10,11,12,13,21,23.
            assert "yolo26" in seen and None not in seen
            assert result.status == AIServiceStatus.UNHEALTHY
            assert result.circuit_state == AIServiceCircuitState.OPEN
            assert result.error_rate_1h == 1.0
```

TDD procedure (one line): for each drafted test, apply the cluster's mutant diff, run the test and confirm the named assert fails (red), revert to original and confirm it passes (green).

## Kill-count estimate

T1 (7 tests) kills G7∪G8∪G9 real members = 40 mutants (every removal AND =None variant across all 7 branches); T2 kills G6 (5); T3 kills G10 (13); T4 kills G1+G2 (15); T5 kills G3 (2); T6 kills G4 (1); T7 kills G11 (1) + most of G5 (10-12). Estimated coverage: 86-89/91 TEST-GAP survivors (G5's getattr-empty-default muts 19/24 need the URL-present setup, which T7's second test provides for 21/23 — 19/24 stay alive unless the same test also exercises an unconfigured-URL run; note that as accepted residue). 8 LOW-VALUE / 12 EQUIVALENT intentionally left.
