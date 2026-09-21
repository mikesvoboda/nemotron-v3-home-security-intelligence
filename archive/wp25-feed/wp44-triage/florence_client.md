# Triage dossier — backend/services/florence_client.py (WP4.3 survivors, gen-2)

- Source: `backend/services/florence_client.py` (1631 lines). Mutant copy: `mutants/backend/services/florence_client.py`.
- Verdict source: `mutants/backend/services/florence_client.py.meta` — 1149 mutants, 520 killed, **629 survived**, 0 unchecked.
- Diff extraction: AST diff of each surviving variant against its `__mutmut_orig` twin (629/629 extracted, 0 missed).
- Covering tests (mutmut-stats `tests_by_mangled_function_name`): primary `backend/tests/unit/services/test_florence_client.py` (640 refs); secondary `test_florence_client_gateway.py` (10), `test_http_connection_pooling.py` (14), `test_business_metrics.py` (21), `test_vision_extractor.py` (92), `test_enrichment_classification_errors.py` (2).

## Headline

The module is a near-perfect 9-endpoint template (extract / batch_extract / ocr / ocr_with_regions / detect / dense_caption / describe_regions / phrase_grounding / detect_security_objects), but **every existing assertion battery was written against the first 3-5 endpoints only**. The survivors are almost entirely the un-asserted tail of the template: per-endpoint circuit-breaker labels, per-endpoint metric labels, per-endpoint payload/URL assertions, 5xx-boundary=500, and error-chain wiring. 377/629 (60%) survivors are TEST-GAP in that template tail.

## Cluster table (counts sum to 629)

| # | cluster | n | class | evidence / what tests miss |
|---|---------|---|-------|----------------------------|
| 1 | MET-pipeline_error-label wrong on non-extract endpoints | 111 | TEST-GAP | record_pipeline_error('<label>') string mutated to None/XX-labelXX/UPPER on ocr, ocr_with_regions, detect, dense_caption, describe_regions, phrase_grounding, detect_security_objects, batch_extract and _check_circuit_breaker. TestMetricsRecording (test_florence_client.py:1107-1236) asserts labels for EXTRACT paths only; per-endpoint labels never asserted. Ex: `::FlorenceClient::batch_extract#30`, `::FlorenceClient::batch_extract#31`, `::FlorenceClient::batch_extract#32` |
| 2 | PAY payload/encoder clobber (all endpoints) | 54 | TEST-GAP | payload dict -> None, key 'image'/'prompt'/'regions'/'phrases'/'items' -> XX..XX/UPPER or removed, image_b64 -> None, encode arg -> None. HTTP Request Verification tests (test_florence_client.py:1240-1330) check payload only for extract/ocr/detect/ocr_with_regions/dense_caption/describe_regions/phrase_grounding basic keys; batch_extract + detect_security_objects payloads NEVER asserted; value correctness (decodable base64, as_dict regions) never asserted -> XXkeyXX/UPPER survive everywhere. Ex: `::FlorenceClient::batch_extract#11`, `::FlorenceClient::batch_extract#12`, `::FlorenceClient::batch_extract#13` |
| 3 | CBK breaker-endpoint arg mutated at call sites | 53 | TEST-GAP | _check_circuit_breaker('<ep>')/_get_breaker('<ep>') -> None/XX/UPPER inside every endpoint method, plus _check_circuit_breaker default endpoint. Wrong arg routes success/failure recording to the extract breaker: endpoint never opens its own breaker and is tripped by unrelated failures. Isolation test covers extract/ocr/detect only. Ex: `::FlorenceClient::_check_circuit_breaker#6`, `::FlorenceClient::_check_circuit_breaker#7`, `::FlorenceClient::_check_circuit_breaker#8` |
| 4 | DUR duration_ms arithmetic clobbered (log-feed only) | 46 | LOW-VALUE | duration_ms = int((time.time()-start)*1000) -> None / /1000 / +start / *1001. value feeds only logger.debug + logger.error extra={} — no metric, no return. Ex: `::FlorenceClient::batch_extract#9`, `::FlorenceClient::dense_caption#62`, `::FlorenceClient::dense_caption#64` |
| 5 | MSG raise/log message text mutated | 29 | LOW-VALUE | f-string messages (raise messages and remaining log args) -> None/removed/arg-swaps. pytest.raises match= strings still hold for the paths they cover ('circuit breaker is open' survives via regex match; full-text identity never asserted). Ex: `::FlorenceClient::batch_extract#33`, `::FlorenceClient::batch_extract#35`, `::FlorenceClient::dense_caption#106` |
| 6 | ERR raise-site original_error kwarg removed | 28 | TEST-GAP | raise FlorenceUnavailableError(msg, original_error=e) -> original_error arg deleted. Tests assert message text only, never .original_error / __cause__ on client-raised errors (the 4 direct-construction tests at :181-210 do not exercise raise sites). Ex: `::FlorenceClient::batch_extract#36`, `::FlorenceClient::dense_caption#105`, `::FlorenceClient::dense_caption#77` |
| 7 | ERR original_error=e -> None | 28 | LOW-VALUE | .original_error becomes None; message text still interpolates {e}. Real but a field nobody's client-side code reads; would be killed by the same drafted cause-assertion as above. Ex: `::FlorenceClient::batch_extract#34`, `::FlorenceClient::dense_caption#103`, `::FlorenceClient::dense_caption#75` |
| 8 | LOGEXC exc_info kwarg mutated | 28 | LOW-VALUE | exc_info=True->None/False/removed on error logs: traceback capture in logs only; nobody asserts logging internals. Ex: `::FlorenceClient::check_health#13`, `::FlorenceClient::check_health#14`, `::FlorenceClient::check_health#16` |
| 9 | CBINIT breaker name= mutated | 27 | LOW-VALUE | CircuitBreaker name -> None/XX/UPPER; name only labels Prometheus circuit-breaker gauges + one init log line. Ex: `::FlorenceClient::__init__#102`, `::FlorenceClient::__init__#103`, `::FlorenceClient::__init__#106` |
| 10 | LOG logger call argument -> None/removed | 25 | EQUIVALENT | logger.debug/warning/info/error(msg) arg -> None or call body deleted: log text only; return values and control flow untouched. Ex: `::FlorenceClient::__init__#185`, `::FlorenceClient::batch_extract#10`, `::FlorenceClient::check_health#2` |
| 11 | LOGEXC extra={} log metadata mutated | 24 | LOW-VALUE | extra={'duration_ms':...,'status_code':...} -> None/removed/key-mutated on logger.error calls in extract's error paths: diagnostic metadata only. Ex: `::FlorenceClient::extract#101`, `::FlorenceClient::extract#102`, `::FlorenceClient::extract#120` |
| 12 | LOG logger message text swaps (XX/UPPER/lower) | 22 | EQUIVALENT | pure message-string rewrites on logger.* calls. Ex: `::FlorenceClient::check_health#3`, `::FlorenceClient::check_health#4`, `::FlorenceClient::check_health#5` |
| 13 | HDR correlation headers dropped on POST/GET | 21 | TEST-GAP | headers=self._get_headers() -> None/absent on check_health GET and every endpoint POST. W3C trace-context (NEM-3147) silently lost; no test asserts the headers value is passed (only presence of the 'headers' key for health :1314-1329). Ex: `::FlorenceClient::batch_extract#23`, `::FlorenceClient::batch_extract#26`, `::FlorenceClient::batch_extract#29` |
| 14 | CFG httpx.Timeout/Limits clobbered in __init__ | 19 | TEST-GAP | connect/read/write/pool= settings.* -> None (client silently unbounded/default httpx timeout), timeout=self._timeout removed, Limits max/keepalive mutated. test_init_timeout_configuration asserts only `is not None` (:265-270); test_http_connection_pooling checks limits for a different construction path. Ex: `::FlorenceClient::__init__#164`, `::FlorenceClient::__init__#166`, `::FlorenceClient::__init__#175` |
| 15 | CBINIT breakers share _cb_config kwarg removed | 16 | TEST-GAP | CircuitBreaker(name=..., config=_cb_config) -> config=None/absent -> breaker uses builtin defaults (threshold 5/30s/3 instead of settings 10/60s/3). Only the _circuit_breaker (extract) alias config is asserted (:1469-1474). Ex: `::FlorenceClient::__init__#101`, `::FlorenceClient::__init__#107`, `::FlorenceClient::__init__#109` |
| 16 | MET florence_task label/task_type derivation | 15 | TEST-GAP | record_florence_task('<ep>') labels on non-extract endpoints mutated + extract's prompt->task_type strip/split/startswith/"extract" fallback mutated. record_florence_task NEVER asserted anywhere; task_type wrong for non-< prompts. Ex: `::FlorenceClient::describe_regions#66`, `::FlorenceClient::describe_regions#67`, `::FlorenceClient::describe_regions#68` |
| 17 | CFG circuit-breaker settings defaults mutated | 13 | EQUIVALENT | getattr(settings,'florence_cb_*',10/60.0/3) default+obj mutated; only bites when settings lacks the attr. test_circuit_breaker_uses_config_settings asserts the alias via fixture-provided values, never the defaults. NOTE: surviving members only tweak the getattr DEFAULT / swap the object where Settings (pydantic) always defines the field (config.py:2052-2069) — the default branch is dead; object->None variants were killed by :1469. Relabeled EQUIVALENT. Ex: `::FlorenceClient::__init__#57`, `::FlorenceClient::__init__#59`, `::FlorenceClient::__init__#62` |
| 18 | CBINIT breakers-dict endpoint KEY mutated | 12 | TEST-GAP | _breakers dict key 'ocr_with_regions'/'dense_caption'/'describe_region'/'phrase_grounding'/'detect_security_objects'/'batch_extract' -> XX..XX/UPPER: that endpoint silently falls back to the extract breaker, breaking isolation. Isolation test (:1416) exercises only extract/ocr/detect. Ex: `::FlorenceClient::__init__#112`, `::FlorenceClient::__init__#113`, `::FlorenceClient::__init__#128` |
| 19 | MET observe_ai_request_duration service label | 12 | TEST-GAP | observe_ai_request_duration('florence_dense_caption'\|'florence_ocr_regions'\|'florence_describe_region'\|'florence_phrase_grounding',...) -> None/XX/UPPER. Tests assert args[0] for florence/florence_ocr/florence_detect only (:1111-1158). Ex: `::FlorenceClient::dense_caption#28`, `::FlorenceClient::dense_caption#32`, `::FlorenceClient::dense_caption#33` |
| 20 | DUR ai_duration clobbered (observe_ai_request_duration feed) | 9 | TEST-GAP | ai_duration = time.time() - ai_start_time mutated per endpoint (9 methods); value is the observation passed to observe_ai_request_duration. extract's test asserts isinstance(args[1], float) (:1111-1126) which survives /1000 and None; other endpoints never assert the duration arg. Ex: `::FlorenceClient::batch_extract#22`, `::FlorenceClient::dense_caption#27`, `::FlorenceClient::describe_regions#26` |
| 21 | PARSE response field defaults mutated (describe_regions) | 9 | TEST-GAP | CaptionedRegion(caption=d.get('caption',''), bbox=d.get('bbox',[])) defaults/keys -> None/''-swap/UPPER: missing-key rows become caption=None/bbox=None. Existing 'missing fields' tests cover ocr_with_regions/detect/dense_caption only (test_florence_client.py:751,887,1021). Ex: `::FlorenceClient::describe_regions#43`, `::FlorenceClient::describe_regions#47`, `::FlorenceClient::describe_regions#49` |
| 22 | ST 5xx boundary >=500 flipped on 3 endpoints | 6 | TEST-GAP | if status_code >= 500 -> >500 / >=501 in ocr_with_regions, dense_caption, phrase_grounding: a 500 response is treated as client error (returns [] instead of raising + breaker failure). 5xx tests for those 3 use 502/503 only; extract has the dedicated 500 case (:448). Ex: `::FlorenceClient::dense_caption#86`, `::FlorenceClient::dense_caption#87`, `::FlorenceClient::ocr_with_regions#86` |
| 23 | URL base_url init rstrip/gateway-default tweaks | 5 | EQUIVALENT | rstrip('/')->rstrip('XX/XX') strips same-or-more from real URLs (no trailing X); getattr 'use_ai_gateway' default False->None/True is dead (Settings always defines the field). Gateway tests keep passing. Ex: `::FlorenceClient::__init__#14`, `::FlorenceClient::__init__#18`, `::FlorenceClient::__init__#24` |
| 24 | ENC base64/mode-membership mutated | 5 | TEST-GAP | 'LA'/'P' -> 'la'/'p'/'XXLAXX' in mode-conversion membership (PIL modes are case-sensitive: LA/P input then crashes in JPEG save) + decode('utf-8')->'UTF-8' (equivalent). Encode tests cover RGB/RGBA/L only (:305-323). Ex: `::FlorenceClient::_encode_image_to_base64#27`, `::FlorenceClient::_encode_image_to_base64#5`, `::FlorenceClient::_encode_image_to_base64#6` |
| 25 | URL endpoint path arg mutated for batch/security post | 4 | TEST-GAP | post URL f'{base}/batch-extract' / f'{base}/detect_security_objects' -> None/removed: request goes nowhere. No test calls batch_extract or detect_security_objects against the mock client at all (batch only exercised via test_vision_extractor). Ex: `::FlorenceClient::batch_extract#24`, `::FlorenceClient::batch_extract#27`, `::FlorenceClient::detect_security_objects#20` |
| 26 | CBQ breaker-state lookup mutations | 3 | TEST-GAP | get_circuit_breaker_state endpoint-is-None flip (named endpoint returns worst-state) and _get_breakers fallback default -> None/removed (AttributeError for unknown endpoints). No test asserts state for a named endpoint or unknown-endpoint fallback. Ex: `::FlorenceClient::get_circuit_breaker_state#1`, `::FlorenceClient::_get_breaker#2`, `::FlorenceClient::_get_breaker#4` |
| 27 | ENC jpeg format/quality cosmetic | 3 | LOW-VALUE | format='JPEG'->'jpeg' (case-insensitive), quality=85->86/removed (default 75): different bytes, same valid JPEG. Ex: `::FlorenceClient::_encode_image_to_base64#18`, `::FlorenceClient::_encode_image_to_base64#20`, `::FlorenceClient::_encode_image_to_base64#21` |
| 28 | NOOP no-op content variants | 2 | EQUIVALENT | _check_circuit_breaker signature-line variants with identical content (docstring/formatting-only under mutmut). Ex: `::FlorenceClient::_check_circuit_breaker#1`, `::FlorenceClient::_check_circuit_breaker#2` |

**Totals: 377 TEST-GAP / 185 LOW-VALUE / 67 EQUIVALENT = 629**

## Drafted kill-tests (UNVERIFIED — not yet run red/green)

All tests target `backend/tests/unit/services/test_florence_client.py`, reuse its `client` / `sample_image` fixtures, and follow its class style. TDD procedure for each: run against the mutant copy (or a hand-applied mutant diff) -> the new assertion FAILS (red); run against the original source -> PASSES (green).

NOTE on imports: T2/T3 need `BatchExtractItem` added to the existing import block (`from backend.services.florence_client import ...` at test_florence_client.py:30-46; base64/io/Image already imported).

### T1 — per-endpoint pipeline-error labels + per-endpoint raise cause (kills MET-pipeline_error-label 111, ERR kwarg-removed 28, ERR-None 28)

```python
class TestPerEndpointErrorMetrics:
    """Kill-mutants: each endpoint must record ITS OWN florence_<ep>_* pipeline-error label
    and must wire original_error on raised FlorenceUnavailableError."""

    ENDPOINTS = [
        # (method name, args builder, 500-vs-4xx label stem)
        ("ocr", lambda img: (img,), "ocr"),
        ("ocr_with_regions", lambda img: (img,), "ocr_regions"),
        ("detect", lambda img: (img,), "detect"),
        ("dense_caption", lambda img: (img,), "dense_caption"),
        ("describe_regions", lambda img: (img, [BoundingBox(x1=0, y1=0, x2=10, y2=10)]), "describe_region"),
        ("phrase_grounding", lambda img: (img, ["person"]), "phrase_grounding"),
        ("detect_security_objects", lambda img: (img,), "security_objects"),
    ]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,args_fn,stem", ENDPOINTS)
    async def test_connection_error_uses_endpoint_specific_label(
        self, client, sample_image, method, args_fn, stem
    ) -> None:
        conn_err = httpx.ConnectError("Connection refused")
        client._http_client.post = AsyncMock(side_effect=conn_err)
        with patch(
            "backend.services.florence_client.record_pipeline_error", autospec=True
        ) as mock_record:
            with pytest.raises(FlorenceUnavailableError) as excinfo:
                await getattr(client, method)(*args_fn(sample_image))
            mock_record.assert_any_call(f"florence_{stem}_connection_error")
        # the raise-site must keep the cause wired (kills `original_error=e` deletion)
        assert excinfo.value.original_error is conn_err
        assert excinfo.value.__cause__ is not None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,args_fn,stem", ENDPOINTS)
    async def test_server_error_uses_endpoint_specific_label(
        self, client, sample_image, method, args_fn, stem
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(), response=mock_response
        )
        client._http_client.post = AsyncMock(return_value=mock_response)
        with patch(
            "backend.services.florence_client.record_pipeline_error", autospec=True
        ) as mock_record:
            with pytest.raises(FlorenceUnavailableError):
                await getattr(client, method)(*args_fn(sample_image))
            mock_record.assert_any_call(f"florence_{stem}_server_error")
```

Red-check: with `record_pipeline_error("florence_ocr_connection_error")` -> `None`/`XX..XX`/`OCR_...`, `assert_any_call` fails.

### T2 — breaker isolation for the untested endpoints (kills CBK 53, CBINIT-key 12, CBQ 3)

```python
class TestPerEndpointBreakerAccounting:
    """Kill-mutants: `_check_circuit_breaker("<ep>")` / `_get_breaker("<ep>")` rewritten to
    None/XX/UPPER silently re-route the endpoint onto the extract breaker (wrong breaker
    opens, wrong breaker records success/failure)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "endpoint,method,args_fn",
        [
            ("ocr_with_regions", "ocr_with_regions", lambda img: (img,)),
            ("dense_caption", "dense_caption", lambda img: (img,)),
            ("describe_region", "describe_regions", lambda img: (img, [BoundingBox(x1=0, y1=0, x2=10, y2=10)])),
            ("phrase_grounding", "phrase_grounding", lambda img: (img, ["person"])),
            ("detect_security_objects", "detect_security_objects", lambda img: (img,)),
            ("batch_extract", "batch_extract", lambda img: ([BatchExtractItem(image=img, prompt="<CAPTION>")],)),
        ],
    )
    async def test_endpoint_opens_its_own_breaker_not_extract(
        self, client, sample_image, endpoint, method, args_fn
    ) -> None:
        from backend.services.circuit_breaker import CircuitState

        client._http_client.post = AsyncMock(side_effect=httpx.ConnectError("nope"))
        threshold = client._breakers[endpoint]._failure_threshold
        for _ in range(threshold):
            with pytest.raises(FlorenceUnavailableError):
                await getattr(client, method)(*args_fn(sample_image))
        # own breaker now OPEN; extract breaker untouched
        assert client._breakers[endpoint].get_state() == CircuitState.OPEN
        assert client._breakers["extract"].get_state() == CircuitState.CLOSED
        # and the next call is rejected with a circuit message (not a connect message)
        with pytest.raises(FlorenceUnavailableError, match=r"[Cc]ircuit"):
            await getattr(client, method)(*args_fn(sample_image))

    @pytest.mark.asyncio
    async def test_success_records_on_named_breaker_only(self, client, sample_image) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"text": "hi"}
        client._http_client.post = AsyncMock(return_value=mock_response)
        client._breakers["ocr"]._failure_count = 4  # near-threshold on ocr only
        await client.ocr(sample_image)
        assert client._breakers["ocr"]._failure_count == 0  # success landed on ocr breaker
        # extract's breaker was NOT touched by ocr success
        assert client._breakers["extract"]._failure_count == 0
```

Red-check: with `_get_breaker("ocr_with_regions")` -> `_get_breaker(None)`, `self._breakers[endpoint]` never sees failures -> `get_state()` stays CLOSED (red). With the dict KEY mutated (`"OCR_WITH_REGIONS":`), `client._breakers[endpoint]` raises KeyError and the whole endpoint silently falls back (red at first loop: state of the real key stays CLOSED while the stray key opens — assertion on `endpoint` fails).

### T3 — batch_extract & detect_security_objects end-to-end payload/URL (kills PAY 54's batch/security tail, URL-endpoint 4, part of ENC)

```python
class TestBatchAndSecurityRequests:
    """batch_extract/detect_security_objects are never exercised against the mock client
    in this file — the batch-extract URL arg, {"items": [...]} payload, {"image": ...} payload
    and security objects URL survive all mutants."""

    @pytest.mark.asyncio
    async def test_batch_extract_sends_url_and_item_payload(self, client, sample_image) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [{"result": "ok", "prompt_used": "<CAPTION>", "inference_time_ms": 5.0}]
        }
        client._http_client.post = AsyncMock(return_value=mock_response)

        items = [BatchExtractItem(image=sample_image, prompt="<CAPTION>")]
        results = await client.batch_extract(items)

        assert results[0].result == "ok"
        assert results[0].prompt_used == "<CAPTION>"
        call = client._http_client.post.call_args
        assert call[0][0] == "http://localhost:8092/batch-extract"
        payload = call[1]["json"]
        assert set(payload.keys()) == {"items"}
        assert set(payload["items"][0].keys()) == {"image", "prompt"}
        # payload image must be a decodable JPEG of the input (kills image_b64=None / encode(None))
        decoded = base64.b64decode(payload["items"][0]["image"])
        assert Image.open(io.BytesIO(decoded)).size == (224, 224)

    @pytest.mark.asyncio
    async def test_detect_security_objects_sends_url_and_parses_result(
        self, client, sample_image
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "detections": [{"label": "person", "bbox": [1, 2, 3, 4], "confidence": 0.9}],
            "objects_queried": ["person", "car"],
        }
        client._http_client.post = AsyncMock(return_value=mock_response)

        res = await client.detect_security_objects(sample_image)

        assert [d.label for d in res.detections] == ["person"]
        assert res.objects_queried == ["person", "car"]
        call = client._http_client.post.call_args
        assert call[0][0] == "http://localhost:8092/detect_security_objects"
        assert set(call[1]["json"].keys()) == {"image"}
```

### T4 — 500 is the exact 5xx boundary on the three endpoints that only test 502/503 (kills ST 6)

```python
class TestServerBoundaryStatus500:
    """status_code >= 500 -> >500/>=501 must be caught: 500 is precisely the boundary and
    these three endpoints' existing 5xx tests use 502/503 only."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,args_fn", [
        ("ocr_with_regions", lambda img: (img,)),
        ("dense_caption", lambda img: (img,)),
        ("phrase_grounding", lambda img: (img, ["person"])),
    ])
    async def test_status_500_raises_not_swallowed(self, client, sample_image, method, args_fn) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(), response=mock_response
        )
        client._http_client.post = AsyncMock(return_value=mock_response)
        with pytest.raises(FlorenceUnavailableError, match="server error"):
            await getattr(client, method)(*args_fn(sample_image))
```

### T5 — per-endpoint Prometheus labels: florence_task + observe_ai_request_duration (kills MET task 15 + observe 12 + DUR-ai 9)

```python
class TestPerEndpointMetricsLabels:
    """record_florence_task is asserted nowhere; observe_ai_request_duration asserted for
    florence/florence_ocr/florence_detect only, and its duration arg never checked for
    plausibility (survives /1000, +start, None)."""

    CASES = [
        ("ocr_with_regions", lambda img: (img,), {"regions": []},
         "ocr_with_regions", "florence_ocr_regions"),
        ("dense_caption", lambda img: (img,), {"regions": []},
         "dense_caption", "florence_dense_caption"),
        ("describe_regions", lambda img: (img, [BoundingBox(x1=0, y1=0, x2=10, y2=10)]),
         {"descriptions": []}, "describe_region", "florence_describe_region"),
        ("phrase_grounding", lambda img: (img, ["person"]),
         {"grounded_phrases": []}, "phrase_grounding", "florence_phrase_grounding"),
        ("detect_security_objects", lambda img: (img,),
         {"detections": [], "objects_queried": []}, "detect_security_objects",
         "florence_detect_security_objects"),
    ]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,args_fn,response,task,observe_label", CASES)
    async def test_endpoint_records_task_and_duration_labels(
        self, client, sample_image, method, args_fn, response, task, observe_label
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = response
        client._http_client.post = AsyncMock(return_value=mock_response)
        with (
            patch("backend.services.florence_client.record_florence_task", autospec=True) as m_task,
            patch(
                "backend.services.florence_client.observe_ai_request_duration", autospec=True
            ) as m_obs,
        ):
            await getattr(client, method)(*args_fn(sample_image))
            m_task.assert_called_once_with(task)
            m_obs.assert_called_once()
            service, seconds = m_obs.call_args[0]
            assert service == observe_label
            assert isinstance(seconds, float) and 0.0 <= seconds < 60.0

    @pytest.mark.asyncio
    async def test_extract_task_type_derivation(self, client, sample_image) -> None:
        """'<CAPTION>' -> caption; bare prompt -> extract (kills the strip/split/startswith mutations)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "x"}
        client._http_client.post = AsyncMock(return_value=mock_response)
        with patch("backend.services.florence_client.record_florence_task", autospec=True) as m_task:
            await client.extract(sample_image, "<VQA>what is this?")
            m_task.assert_called_once_with("vqa")
            m_task.reset_mock()
            await client.extract(sample_image, "plain prompt")
            m_task.assert_called_once_with("extract")
```

### T6 — correlation headers actually passed on every request (kills HDR 21)

```python
class TestCorrelationHeadersForwarded:
    """headers=None on the POST/GET calls silently drops W3C trace context (NEM-3147);
    only health's `headers in kwargs` presence is checked today (:1314-1329)."""

    @pytest.mark.asyncio
    async def test_all_posts_send_correlation_headers(self, client, sample_image) -> None:
        expected = {"traceparent": "00-test", "x-correlation-id": "cid-1"}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "x", "text": "x", "regions": [],
                                          "detections": [], "descriptions": [],
                                          "grounded_phrases": []}
        client._http_client.post = AsyncMock(return_value=mock_response)
        with patch(
            "backend.services.florence_client.get_correlation_headers", return_value=expected, autospec=True
        ):
            await client.extract(sample_image, "<CAPTION>")
            assert client._http_client.post.call_args[1]["headers"] == expected
            await client.ocr(sample_image)
            assert client._http_client.post.call_args[1]["headers"] == expected
            await client.detect(sample_image)
            assert client._http_client.post.call_args[1]["headers"] == expected
```

(`get_correlation_headers` is module-imported at florence_client.py:33 — patch target `backend.services.florence_client.get_correlation_headers`. If the module turns out to call it through `_get_headers`, patch that instead; red/green run will confirm the seam. UNVERIFIED.)

### T7 (bonus, cheap) — describe_regions missing-field defaults (kills PARSE 9)

```python
    @pytest.mark.asyncio
    async def test_describe_regions_handles_missing_fields(self, client, sample_image) -> None:
        """Mirror of the ocr_with_regions/detect/dense_caption missing-field tests (:751,:887,:1021)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"descriptions": [{"caption": "only caption"}]}
        client._http_client.post = AsyncMock(return_value=mock_response)
        regions = [BoundingBox(x1=0, y1=0, x2=10, y2=10)]
        out = await client.describe_regions(sample_image, regions)
        assert out[0].caption == "only caption"
        assert out[0].bbox == []
```

## Verdict roll-up

- 629 survivors = 377 TEST-GAP / 185 LOW-VALUE / 67 EQUIVALENT.
- The 7 drafted tests above (T1-T6 = the 6 highest-value clusters; T7 bonus) target clusters totalling 377 - (residual metric-label families without drafted tests) and cover, in priority order: per-endpoint pipeline labels (111), payload/URL template tail incl. batch/security (54+4), breaker endpoint accounting (53+12+3), error cause wiring (56), 500-boundary (6), per-endpoint Prometheus labels (36 incl. duration feed 9), and headers (21).
- Residual TEST-GAP families (CFG httpx timeouts 19, CBINIT config-kwarg 16, ENC mode-set 5) are each 1-3 assertion additions to `TestFlorenceClientInit`/`TestEncodeImageToBase64` (assert `client._timeout.read == settings value`, assert `b._config.failure_threshold` on 2-3 non-extract breakers, encode a mode="P" image). Not drafted in full to keep this dossier at the 6-test budget; the assertion line is noted in each cluster's evidence cell.
