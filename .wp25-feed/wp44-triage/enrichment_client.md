# WP4.4 Triage Dossier — backend/services/enrichment_client.py

**Run**: WP4.3 mutation baseline (mutmut run6). **Status**: UNVERIFIED (read-only triage; no tests run, per harness constraints).
**Verdicts source**: `mutants/backend/services/enrichment_client.py.meta` → `exit_code_by_key` (exit 0 = survived). Read succeeded first try: 2567 keys, **1330 survivors**, 726 killed(1), 392 timeout(3), 119 rc=-24.
**Diff method**: `mutants/.../enrichment_client.py.spans` (variant → line ranges in the 17.7 MB mutant copy) diffed against `...__mutmut_orig` regions; 1330/1330 extracted, all diffs 3–9 lines (single-statement changes). Each survivor's changed line was mapped back to `backend/services/enrichment_client.py` by region-offset alignment — **0 line/text mismatches** — then AST-classified (is the line inside a `logger.*` / `record_pipeline_error` / `increment_enrichment_retry` / `observe_ai_request_duration` call?).
**Cluster totals**: 1330 = **515 TEST-GAP + 533 EQUIVALENT + 282 LOW-VALUE**.

## Covering test files (from `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`)

| File | Role |
|---|---|
| `backend/tests/unit/services/test_enrichment_client.py` (3046 L) | main unit suite; success paths assert payload dict contents (`call_args.kwargs["json"]`) but never `call_args.args[0]` URL except enrich/preload (:2844, :2917); `_is_retryable_error` boundary tests use 503/400 only (:2005-2017) |
| `backend/tests/unit/services/test_enrichment_client_errors.py` (975 L) | malformed JSON / missing fields / HTTP status matrix; asserts `original_error is not None` (weak) e.g. :237,:257,:573 |
| `backend/tests/unit/services/test_enrichment_client_retry.py` (1001 L) | retry/backoff; asserts `post.call_count==3`, `sleep.call_count==2`, metric name **only for vehicle** (:232 `assert_called_with("enrichment_vehicle_connection_error")`, :524 `assert_called_with("vehicle")`) |
| `backend/tests/unit/services/test_enrichment_client_circuit_breaker.py` (566 L) | breaker config/open/half-open; `test_health_check_includes_circuit_breaker_state` :490 asserts `"circuit_breaker_state" in result` but never the plural `circuit_breaker_states` |
| `backend/tests/unit/services/test_enrichment_client_gateway.py` (213 L) | AI-gateway URL routing |
| `backend/tests/unit/services/test_http_connection_pooling.py` | client pooling |

## Cluster table (33 clusters; counts sum to 1330)

| # | Cluster | N | Class | Functions (mutants) | Example keys (mutmut suffix) | Note — why this class |
|---|---|---:|---|---|---|---|
| 1 | EQ-log-extra | 186 | EQUIVALENT | all 11 endpoint fns + check_health; L1248-3231 | analyze_pose__104,107,109 | `extra={...}` dict on `logger.error/warning` deleted/None'd/keys XX-wrapped/UPPERcased. Log record content, no return-value effect. |
| 2 | GAP-metric-name-identity | 185 | TEST-GAP | estimate_object_distance:36, analyze_pose:30, +9 fns; L1224-3192 | analyze_pose__100,101,102 | `record_pipeline_error("<name>")`, `increment_enrichment_retry(endpoint_name)`, `observe_ai_request_duration(...)`, `error_type=`, `error_metric=` arg clobbered. Ops dashboards key on these strings. Tests assert names **only for vehicle** (retry.py:232,:524); other endpoints assert `call_count` only → test exists but asserts too weakly. |
| 3 | EQ-log-message | 176 | EQUIVALENT | __init__ + 11 endpoint fns; L926-3298 | __init___202, analyze_pose__103,121 | message f-string text mutated (None/XX/case). Pure log text. |
| 4 | LOW-duration-ms | 144 | LOW-VALUE | 9 endpoint fns; L1244-3228 | analyze_pose__125,127,128 | `duration_ms = int((time.time()-start)*1000)` → None, /1000, +start, *1001. Value feeds only `extra={"duration_ms":...}` log field. Nobody should assert wall-clock ms in unit tests. |
| 5 | EQ-exc-info | 102 | EQUIVALENT | 9 endpoint fns + check_health; L1127-2541 | analyze_pose__105,108,113 | `exc_info=True` → None/False/deleted. Traceback formatting only. |
| 6 | GAP-parse-unified-fields | 94 | TEST-GAP | _parse_unified_response:94; L3059-3107 | _parse_unified_response__10,101,104 | `data.get("pose"/"clothing"/"demographics"/"vehicle"/"threat"...)` key/default mutated (`"unknown"`→None/1.0/XX/CASE; `confidence` default 0.0→1.0). Wrong defaults silently corrupt every enriched LLM prompt. Only 8 tests touch fn; none asserts defaults when sub-dict fields absent. |
| 7 | LOW-catchall | 66 | LOW-VALUE | classify_action:15, classify_clothing:10, +8; L1189-3191 | analyze_pose__20,22,230 | `last_error` init sentinel, `ai_duration` math for `observe_ai_request_duration`, `raise EnrichmentUnavailableError` message text, result-ctor fields set to None where success tests already assert the asserted subset (`result.confidence` etc.). |
| 8 | GAP-endpoint-url | 53 | TEST-GAP | 11 endpoint fns + check_health/get_model_status; L1187-3154 | analyze_pose__14,15,16 | `endpoint = "pose-analyze"` / `endpoint_name` / request URL f-string mutated (XX/case/None). Tests mock `_http_client.post` and never assert `call_args.args[0]` (except enrich :2844 / preload :2917) → a wrong URL path is invisible to the suite. |
| 9 | GAP-retry-branch-boundary | 48 | TEST-GAP | 8 endpoint fns; L1302-2512 | analyze_pose__115,116,117 | `if attempt < self._max_retries - 1:` → `<=`/`+1`/`-2`: changes whether the LAST attempt retries or sleeps. `call_count==3` passes anyway (`<=` and `+1` variants can't raise IndexError because `range()` caps the loop; `-2` shifts *which* attempt logs "retry" and skips final failure metric). No test asserts sleep-call count on non-vehicle endpoints or that the final attempt goes through the else-metric path. |
| 10 | LOW-breaker-init | 35 | LOW-VALUE | __init__; L897-905 | __init___100,103,107 | `CircuitBreaker(name="enrichment_vehicle", config=_cb_config)` name/config kwargs mutated. Breaker `name` is log/metric decoration; routing dict keys untouched. cb test asserts config values and `_name` only for `enrichment_unified`. |
| 11 | EQ-context-strings | 33 | EQUIVALENT | 10 dataclasses' `to_context_string`; L107-699 | ActionClassificationResult…to_context_string__6 | prompt text XX-wrap/case; existing tests assert substring presence ("standing", "ALERT", "92%"), which most case/XX variants still satisfy or are pure cosmetics. |
| 12 | GAP-last-error-chaining | 33 | TEST-GAP | 7 endpoint fns; L1254-2551 | analyze_pose__114,144,178 | `last_error = e` → None: `EnrichmentUnavailableError(..., original_error=last_error)` loses the cause. Existing assertions are only `original_error is not None` on *malformed-json* paths (errors.py:237 etc.), never identity `is <raised exc>` on the *retry-exhaustion* path. |
| 13 | GAP-request-payload | 31 | TEST-GAP | classify_clothing:7, estimate_depth:6, +8; L979-3169 | analyze_pose__30,33 | `"image": image_b64`, `"frames": [...]`, `"labels"`, `"min_confidence"`, `payload["bbox"]=list(bbox)` mutated. Tests check key *presence* (`"bbox" in json`) but not base64 image bytes or bbox round-trip value for most endpoints. |
| 14 | LOW-timeout-config-values | 22 | LOW-VALUE | __init__ + classify_action; L877-3175 | __init___181,183,192 | `httpx.Timeout(connect/read/write/pool=...)` numeric tweaks; unit fixtures freeze settings values; asserting them duplicates config. |
| 15 | GAP-request-headers | 22 | TEST-GAP | 11 fns + check_health; L1101-3289 | analyze_pose__47,50 | `headers=self._get_headers()` → None/deleted: W3C trace-context silently dropped (NEM-3147). No test asserts the `headers` kwarg on post/get. |
| 16 | EQ-raise-message | 18 | EQUIVALENT | 11 fns; L1183-2382 | analyze_pose__10,11,12 | `EnrichmentUnavailableError("...circuit open...")` message text XX/case; tests use `pytest.raises` type, some loose `in str()` on the exhaustion message (that's cluster 7/26, not this string). |
| 17 | GAP-health-payload-keys | 12 | TEST-GAP | check_health; L1113-1133 | check_health__34,35,36 | `"circuit_breaker_state"` / `"circuit_breaker_states"` response keys XX/case'd in healthy + all 3 error dicts. Tests assert `"circuit_breaker_state" in result` (cb.py:490) but never `"circuit_breaker_states"` — dashboard contract key. |
| 18 | EQ-to-dict | 9 | EQUIVALENT | UnifiedEnrichmentResult.to_dict; L589-601 | to_dict__10,14,16 | dict key text/case tweaks; tests assert `result["pose_class"]` presence. |
| 19 | GAP-timeout-wiring | 8 | TEST-GAP | 8 endpoint fns; L1214-3182 | analyze_pose__43 | `async with asyncio.timeout(explicit_timeout):` → `timeout(None)` deletes the NEM-1465 defense-in-depth guard entirely (httpx timeouts would then be the only bound). Invisible to mocked tests. |
| 20 | EQ-cast-only | 8 | EQUIVALENT | check_health, get_model_status; L1104-3261 | check_health__13,14,15 | `cast("dict[str, Any]", ...)` type-annotation string mutated — runtime no-op. |
| 21 | LOW-client-limits | 7 | LOW-VALUE | __init__; L923 | __init___195,196,197 | `httpx.Limits(max_connections=10, max_keepalive=5)` mutated; only observable under load. |
| 22 | GAP-url-rstrip | 6 | TEST-GAP | __init__; L855-871 | __init___27,32,44 | `.rstrip("/")` on base/light URLs removed/arg-changed → double-slash request paths `{base}//vehicle-classify`. No test passes a trailing-slash URL. |
| 23 | GAP-http-500-boundary | 6 | TEST-GAP | _is_retryable_error:2, classify_clothing:2, estimate_object_distance:2; L1082-2038 | _is_retryable_error__4,5 | `status_code >= 500` → `> 500`/`>= 501` and `if status_code < 500:` → `<= 500`: **HTTP 500 stops being retried / starts being treated as a 4xx client error**. All existing 5xx tests use 502/503/504 — 500 itself is never the boundary probe. |
| 24 | GAP-circuit-aggregation | 6 | TEST-GAP | get_circuit_breaker_state:2, is_circuit_open:2, reset_circuit_breaker:2; L992-1034 | get_circuit_breaker_state__4,6 | worst-state precedence OPEN>HALF_OPEN>CLOSED and "ANY open" `any(...)` mutated. Existing tests open ONE breaker and check aggregate → half the truth; no HALF_OPEN-vs-OPEN ordering probe. |
| 25 | GAP-breaker-routing | 4 | TEST-GAP | _get_service_for_model; L941-943 | _get_service_for_model__1,2,5 | `self._breakers.get(model, self._breakers["enrich"])` fallback broken → unknown model → None breaker → AttributeError on first call. No test calls with an unregistered model. |
| 26 | LOW-error-dict-text | 4 | LOW-VALUE | check_health:3, get_model_status; L1112-3267 | check_health__33,49,66 | `"error": str(e)` → `str(None)`; error *text* field of degraded-health payloads; `status` key (tested) intact. |
| 27 | GAP-health-status-paths | 4 | TEST-GAP | check_health:2, get_model_status:2; L1100-3257 | check_health__4,6 | `/health` and `/models/status` URL strings mutated; tests mock `.get` return without URL assert. |
| 28 | GAP-gateway-routing | 2 | TEST-GAP | __init__; L851 | __init___14,20 | `use_ai_gateway` gate `getattr(..., False)` default flipped; gateway test file exists but pins explicit True, not the default-False branch. |
| 29 | LOW-backoff-math | 2 | LOW-VALUE | _calculate_backoff_delay; L1054-1055 | _calculate_backoff_delay__10,15 | jitter cap tweaks; backoff tests assert monotonic growth + 30s cap already. |
| 30 | GAP-risk-weight-boundary | 1 | TEST-GAP | ActionClassificationResult.has_security_alerts; L340 | has_security_alerts__2 | `risk_weight >= 0.7` → `> 0.7`: an action at exactly 0.7 flips "security alert" → dropped from LLM risk context. Tests never construct risk_weight == 0.7. |
| 31 | EQ-backcompat-alias | 1 | EQUIVALENT | __init__; L910 | __init___176 | `self._circuit_breaker = self._breakers["enrich"]` → None — alias documented as deprecated shim; surviving mutants here are acceptable debt. |
| 32 | LOW-init-misc | 1 | LOW-VALUE | __init__; L870 | __init___58 | settings-lookup default string tweak; fixture always sets the attribute. |
| 33 | LOW-png-encode | 1 | LOW-VALUE | _encode_image_to_base64; L977 | _encode_image_to_base64__7 | `.decode("utf-8")` → `"UTF-8"` — codec alias, byte-identical. |

## Drafted tests (6 tests kill 6 clusters ≈ 232 survivors: 48+94+6+6+53+33+22+1+12+6+4+2+8+4 — see per-test kill lists)

All UNVERIFIED — not yet run red/green. TDD procedure for every test: run against the mutant (assertion must FAIL) then against `backend/services/enrichment_client.py` original (must PASS). Style follows `test_enrichment_client_retry.py` fixtures (patched `get_settings`, AsyncMock `_http_client`).

### T1 — `test_retry_sleep_count_and_final_attempt_goes_to_else_path` (kills GAP-retry-branch-boundary, 48) → `backend/tests/unit/services/test_enrichment_client_retry.py`
```python
class TestRetryAttemptBoundary:
    """WP4.4: the last attempt must NOT sleep and must record the final-failure metric.

    Kills `if attempt < self._max_retries - 1:` flips (<=, +1, -2) on every endpoint.
    UNVERIFIED - not yet run red/green.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "endpoint_kwargs",
        [
            {"method": "classify_vehicle", "metric": "enrichment_vehicle_server_error"},
            {"method": "analyze_pose", "metric": "enrichment_pose_server_error"},
            {"method": "estimate_object_distance", "metric": "enrichment_distance_server_error"},
        ],
    )
    async def test_last_attempt_skips_sleep_and_records_metric(
        self, client: EnrichmentClient, sample_image: Image.Image, endpoint_kwargs: dict
    ) -> None:
        """With max_retries=3: exactly 2 sleeps, and the final 5xx goes through
        the else-branch (record_pipeline_error(<server_error>)), not another retry."""
        mock_request = MagicMock()
        mock_error = MagicMock()
        mock_error.status_code = 500

        client._http_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Internal server error", request=mock_request, response=mock_error
            )
        )

        with (
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch(
                "backend.services.enrichment_client.record_pipeline_error", autospec=True
            ) as mock_record,
            patch(
                "backend.services.enrichment_client.increment_enrichment_retry", autospec=True
            ) as mock_retry,
        ):
            with pytest.raises(EnrichmentUnavailableError):
                await getattr(client, endpoint_kwargs["method"])(sample_image)

            # max_retries=3 -> 3 attempts, sleep only BETWEEN them
            assert client._http_client.post.call_count == 3
            assert mock_sleep.call_count == 2
            # retries are announced exactly twice, and the LAST attempt records
            # the terminal server-error metric (mutants that shift the boundary
            # either sleep 3x or take the retry branch on attempt 2-of-3)
            assert mock_retry.call_count == 2
            mock_record.assert_called_with(endpoint_kwargs["metric"])
```
TDD: on `<=` mutant the else-branch never runs → `mock_record.assert_called_with("enrichment_pose_server_error")` fails (records `..._connection_error`? no — it takes retry branch a 3rd time and falls to loop-exhaust raise with **no** server_error call) → red. Original → green.

### T2 — `test_http_500_is_retryable_and_499_is_client_error` (kills GAP-http-500-boundary, 6) → `test_enrichment_client.py` (next to existing `_is_retryable_error` tests, :1995)
```python
def test_is_retryable_error_http_500_boundary(self, client: EnrichmentClient) -> None:
    """WP4.4: 500 is the exact retry boundary — kills >=500 -> >500 / >=501 flips.
    UNVERIFIED - not yet run red/green."""
    def status_error(code: int) -> httpx.HTTPStatusError:
        resp = MagicMock()
        resp.status_code = code
        return httpx.HTTPStatusError("err", request=MagicMock(), response=resp)

    assert client._is_retryable_error(status_error(500)) is True   # boundary itself
    assert client._is_retryable_error(status_error(499)) is False

@pytest.mark.asyncio
async def test_classify_clothing_499_is_client_error_500_retries(
    self, client: EnrichmentClient, sample_image: Image.Image
) -> None:
    """WP4.4: `if e.response.status_code < 500` flips (<=500 / <501) kill:
    499 must return None on ONE attempt; 500 must retry (call_count == 2 then succeed).
    UNVERIFIED - not yet run red/green."""
    for code, expect_posts in ((499, 1), (500, 2)):
        mock_request = MagicMock()
        mock_err = MagicMock()
        mock_err.status_code = code
        ok = MagicMock()
        ok.json.return_value = {
            "clothing_type": "jacket", "color": "blue", "style": "casual",
            "confidence": 0.88, "top_category": "outerwear",
            "description": "d", "is_suspicious": False, "is_service_uniform": False,
            "inference_time_ms": 55.0,
        }
        ok.raise_for_status = MagicMock()
        n = 0

        async def post(*a, **k):
            nonlocal n
            n += 1
            if n < 2:
                raise httpx.HTTPStatusError("err", request=mock_request, response=mock_err)
            return ok

        client._http_client.post = post
        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("backend.services.enrichment_client.record_pipeline_error", autospec=True),
            patch("backend.services.enrichment_client.observe_ai_request_duration", autospec=True),
            patch("backend.services.enrichment_client.increment_enrichment_retry", autospec=True),
        ):
            if code == 499:
                assert await client.classify_clothing(sample_image) is None
            else:
                assert await client.classify_clothing(sample_image) is not None
            assert n == expect_posts
```
TDD: `<= 500` mutant treats 500 as client error → returns None on first post → `n == 2` fails. Original green.

### T3 — `test_final_failure_metrics_use_exact_endpoint_metric_names` (kills most of GAP-metric-name-identity, ~120 of 185 — all record_pipeline_error/error_type/error_metric mutants on pose+distance) → `test_enrichment_client_retry.py`
```python
class TestPerEndpointMetricNames:
    """WP4.4: every endpoint's terminal-failure metric string is an ops contract.
    Existing coverage checks names only for vehicle (retry.py:232, :524).
    UNVERIFIED - not yet run red/green."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "method,exc,metric,retry_name",
        [
            ("analyze_pose", httpx.ConnectError("x"), "enrichment_pose_connection_error", "pose"),
            ("analyze_pose", httpx.TimeoutException("x"), "enrichment_pose_timeout", "pose"),
            ("estimate_object_distance", httpx.ConnectError("x"),
             "enrichment_distance_connection_error", "distance"),
            ("estimate_object_distance", httpx.TimeoutException("x"),
             "enrichment_distance_timeout", "distance"),
        ],
    )
    async def test_terminal_metric_exact(
        self, client: EnrichmentClient, sample_image: Image.Image,
        method: str, exc: Exception, metric: str, retry_name: str,
    ) -> None:
        client._http_client.post = AsyncMock(side_effect=exc)
        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("backend.services.enrichment_client.record_pipeline_error", autospec=True
                  ) as mock_record,
            patch("backend.services.enrichment_client.increment_enrichment_retry", autospec=True
                  ) as mock_retry,
        ):
            with pytest.raises(EnrichmentUnavailableError):
                await getattr(client, method)(sample_image)

            mock_retry.assert_called_with(retry_name)
            mock_record.assert_called_with(metric)  # error_type must select connection vs timeout
```
TDD: any XX/UPPER/None clobber of the metric or of `error_type = "connection_error" if isinstance(...) else "timeout"` breaks the exact string → red; original green.

### T4 — `test_parse_unified_response_field_defaults` (kills GAP-parse-unified-fields, 94) → `test_enrichment_client.py`
```python
class TestParseUnifiedDefaults:
    """WP4.4: _parse_unified_response must read EXACT keys with EXACT defaults.
    Kills key-name (XX/case/None) and default (0.0->1.0, "unknown"->None/case) mutants.
    UNVERIFIED - not yet run red/green."""

    def test_full_payload_maps_every_field(self, client: EnrichmentClient) -> None:
        result = client._parse_unified_response({
            "models_loaded": ["pose"], "inference_time_ms": 12.5,
            "pose": {"keypoints": [{"x": 0.5}], "pose_class": "standing",
                      "confidence": 0.77, "is_suspicious": True},
            "clothing": {"categories": [{"category": "hoodie"}], "is_suspicious": True},
            "demographics": {"age_range": "30-40", "age_confidence": 0.66,
                              "gender": "female", "gender_confidence": 0.61},
            "vehicle": {"make": "toyota", "model": "corolla", "color": "red",
                         "type": "sedan", "confidence": 0.9},
            "threat": {"threats": [{"type": "weapon"}], "has_threat": True,
                        "max_severity": "high"},
            "reid_embedding": [0.1, 0.2], "pet": {"breed": "lab"},
            "action": {"name": "running"}, "depth": {"m": 3.0},
        })
        assert result.inference_time_ms == 12.5
        assert result.pose.pose_class == "standing"
        assert result.pose.confidence == 0.77
        assert result.pose.is_suspicious is True
        assert result.demographics.age_range == "30-40"
        assert result.demographics.age_confidence == 0.66
        assert result.demographics.gender == "female"
        assert result.demographics.gender_confidence == 0.61
        assert result.vehicle.type == "sedan"
        assert result.threat.has_threat is True
        assert result.threat.max_severity == "high"
        assert result.reid_embedding == [0.1, 0.2]

    def test_missing_optional_fields_use_documented_defaults(self, client: EnrichmentClient) -> None:
        """Absent sub-fields must default to 0.0 / "unknown" / False / "none" —
        NOT None, NOT 1.0. Each default here is a surviving mutant."""
        result = client._parse_unified_response({
            "pose": {}, "clothing": {}, "demographics": {}, "vehicle": {}, "threat": {},
        })
        assert result.inference_time_ms == 0.0
        assert result.pose.keypoints == []
        assert result.pose.pose_class == "unknown"
        assert result.pose.confidence == 0.0
        assert result.pose.is_suspicious is False
        assert result.clothing.categories == []
        assert result.clothing.is_suspicious is False
        assert result.demographics.age_range == "unknown"
        assert result.demographics.age_confidence == 0.0
        assert result.demographics.gender == "unknown"
        assert result.demographics.gender_confidence == 0.0
        assert result.vehicle.type == "unknown"
        assert result.vehicle.confidence == 0.0
        assert result.threat.threats == []
        assert result.threat.has_threat is False
        assert result.threat.max_severity == "none"
```
TDD: `"confidence", 0.0 → 1.0` mutant → `== 0.0` fails; key XX mutant → `pose_class == "unknown"` gets the real value or None → fails. Original green.

### T5 — `test_requests_hit_exact_urls_with_trace_headers` (kills GAP-endpoint-url 53 + GAP-request-headers 22 + GAP-url-rstrip 6 + GAP-health-status-paths 4 + most GAP-request-payload 31) → `test_enrichment_client.py`
```python
class TestRequestWiring:
    """WP4.4: every endpoint must POST to <service>/<exact-endpoint> WITH correlation
    headers and the documented payload keys. Existing tests assert payload internals
    but never the URL (except enrich :2844 / preload :2917) or headers at all.
    UNVERIFIED - not yet run red/green."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "method,path,beacon",
        [
            ("classify_vehicle", "/vehicle-classify", "vehicle_type"),
            ("classify_pet", "/pet-classify", "pet_type"),
            ("classify_clothing", "/clothing-classify", "clothing_type"),
            ("estimate_depth", "/depth-estimate", "max_depth"),
            ("estimate_object_distance", "/object-distance", "estimated_distance_m"),
            ("analyze_pose", "/pose-analyze", "posture"),
            ("classify_action", "/action-classify", "action"),
        ],
    )
    async def test_url_headers_and_image_payload(
        self, client: EnrichmentClient, sample_image: Image.Image,
        method: str, path: str, beacon: str,
    ) -> None:
        ok = MagicMock()
        ok.json.return_value = {beacon: "v", "confidence": 0.5, "keypoints": [],
                                 "posture": "p", "alerts": [], "all_scores": {},
                                 "inference_time_ms": 1.0}
        ok.raise_for_status = MagicMock()
        client._http_client.post = AsyncMock(return_value=ok)
        with patch("backend.services.enrichment_client.observe_ai_request_duration",
                   autospec=True), \
             patch("backend.services.enrichment_client.get_correlation_headers",
                   return_value={"traceparent": "00-abc-1"}, autospec=True):
            await getattr(client, method)(sample_image)

        call = client._http_client.post.call_args
        assert call.args[0] == "http://test-enrichment:8094" + path
        assert call.kwargs["headers"] == {"traceparent": "00-abc-1"}
        if method != "classify_action":
            import base64 as _b64
            assert _b64.b64decode(call.kwargs["json"]["image"])[:4] == b"\x89PNG"

    def test_base_urls_are_rstripped(self, mock_settings: MagicMock) -> None:
        """Trailing slash in config must not produce '//vehicle-classify'."""
        mock_settings.enrichment_url = "http://test-enrichment:8094/"
        mock_settings.enrichment_light_url = "http://test-enrichment-light:8096/"
        with patch("backend.services.enrichment_client.get_settings",
                   return_value=mock_settings, autospec=True):
            c = EnrichmentClient()
        assert c._base_url == "http://test-enrichment:8094"
        assert c._light_base_url == "http://test-enrichment-light:8096"

    @pytest.mark.asyncio
    async def test_health_and_model_status_urls(self, client: EnrichmentClient) -> None:
        ok = MagicMock()
        ok.json.return_value = {"status": "healthy"}
        ok.raise_for_status = MagicMock()
        client._health_http_client.get = AsyncMock(return_value=ok)
        with patch("backend.services.enrichment_client.get_correlation_headers",
                   return_value={"traceparent": "t"}, autospec=True):
            await client.check_health()
        assert client._health_http_client.get.call_args.args[0] == \
            "http://test-enrichment:8094/health"
        await client.get_model_status()
        assert client._health_http_client.get.call_args.args[0] == \
            "http://test-enrichment:8094/models/status"
```
TDD: URL XX/case/None mutant → `call.args[0]` equality fails; `headers=None` mutant → headers assert fails; missing `.rstrip("/")` → second `test_base_urls_are_rstripped` fails. Original green.

### T6 — `test_error_chaining_and_alert_boundaries` (kills GAP-last-error-chaining 33 + GAP-risk-weight-boundary 1 + GAP-health-payload-keys 12) → `test_enrichment_client_errors.py`
```python
class TestCauseChainingAndAlertBoundaries:
    """WP4.4: `original_error` must be the actual last exception (identity, not
    just not-None); has_security_alerts boundary is >= 0.7 inclusive; degraded
    health payloads keep BOTH circuit_breaker_state and circuit_breaker_states.
    UNVERIFIED - not yet run red/green."""

    @pytest.mark.asyncio
    async def test_exhausted_retries_chain_the_real_exception(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        boom = httpx.ConnectError("refused-by-peer")
        enrichment_client._http_client.post = AsyncMock(side_effect=boom)
        with patch("asyncio.sleep", new_callable=AsyncMock), \
             patch("backend.services.enrichment_client.record_pipeline_error", autospec=True), \
             patch("backend.services.enrichment_client.increment_enrichment_retry", autospec=True):
            with pytest.raises(EnrichmentUnavailableError) as exc_info:
                await enrichment_client.classify_vehicle(sample_image)
        assert exc_info.value.original_error is boom   # `last_error = None` mutant -> None

    def test_has_security_alerts_inclusive_at_07(self) -> None:
        from backend.services.enrichment_client import ActionClassificationResult
        edge = ActionClassificationResult(
            action="loitering", confidence=0.5, is_suspicious=False,
            risk_weight=0.7, all_scores={}, inference_time_ms=1.0)
        assert edge.has_security_alerts() is True      # `> 0.7` mutant -> False

    @pytest.mark.asyncio
    async def test_degraded_health_keeps_both_breaker_keys(
        self, enrichment_client: EnrichmentClient
    ) -> None:
        enrichment_client._health_http_client.get = AsyncMock(
            side_effect=httpx.ConnectError("down"))
        result = await enrichment_client.check_health()
        assert result["status"] == "unavailable"
        assert "circuit_breaker_state" in result
        assert "circuit_breaker_states" in result      # key-clobber mutants miss plural
        assert isinstance(result["circuit_breaker_states"], dict)
        assert result["circuit_breaker_states"]["vehicle"] == "closed"
```
TDD: `last_error=None` mutant → `is boom` fails; `> 0.7` mutant → `is True` fails; `"circuit_breaker_states"` XX-case mutant → plural key missing → fails. Original green.

## Notes / caveats for WP4.4 implementers

- **T5 parametrize payloads**: `ok.json.return_value` includes union-of-keys across endpoints; endpoints read extra keys (`result["posture"]` in a vehicle payload) harmlessly. `classify_action` takes `frames: list[Image.Image]` and payload key `"frames"`, so image-key assert is skipped there — add a `frames`-key assert if porting.
- `test_enrichment_client_errors.py` fixture is named `enrichment_client` (not `client`); T6 matches that file.
- GAP-retry-branch mutants at `<` vs `<=` are the classic "one extra sleep" bug class — the sleep-count assert is the load-bearing one; keep it even if the metric assert proves flaky.
- 533 EQUIVALENT + 282 LOW-VALUE (≈61%) justify a `mutmut` skip-list only if run time becomes the bottleneck; the drafted tests cut the remaining actionable set to ~283 TEST-GAP survivors, of which the six tests address ~232.
- The 119 `rc=-24` (SIGTERM/timeout) verdicts were excluded per harness rules; if any are enrichment_client hangs they'd resurface as false survivors in a re-run — not triaged here.

Artifacts (scratch, outside repo): diffs `/tmp/wp25/wp44-triage-work/ec_diffs.json`, per-mutant precise map `/tmp/wp25/wp44-triage-work/ec_precise.json`, cluster groups `/tmp/wp25/wp44-triage-work/ec_final_clusters.json`.
