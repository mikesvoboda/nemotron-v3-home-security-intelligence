# WP4.4 Triage Dossier — backend/services/detector_client.py

Surviving mutants: **839** of 1376 (killed 537). Verdict source:
`mutants/backend/services/detector_client.py.meta` (`exit_code_by_key`, 0 = survived).
Mutant diffs reconstructed from `mutants/backend/services/detector_client.py` + `.spans`
(`mutmut show` could not resolve the `ǁ`-mangled keys — FileNotFoundError; manual span-diff used).

## Covering test files (from mutants/mutmut-stats.json tests_by_mangled_function_name)

- `backend/tests/unit/services/test_detector_client.py` (2485 lines; 55 tests cover
  `detect_objects`, 45 cover `_send_detection_request`, 13 cover `_validate_image_for_detection`)
- `backend/tests/unit/services/test_model_warmup.py` (all coverage for `get_warmth_state`,
  `is_cold`, `warmup`, `model_readiness_probe`; the only DetectorClient warmth test is
  `test_get_warmth_state_returns_correct_structure` at line 340)
- `backend/tests/unit/services/test_detector_client_segmentation.py` (sole coverage for `segment_image`)
- `backend/tests/unit/api/middleware/test_correlation_propagation.py` (header tests; uses **str** api key, line 233)
- `backend/tests/unit/services/test_ai_inference_semaphore.py`,
  `test_frame_buffer_pipeline_integration.py`, `test_detector_client_gateway.py`,
  `test_http_connection_pooling.py` (construction-path coverage)

## Cluster table (counts sum to 839)

| # | Cluster (function / concern) | N | Class | Example keys (≤3) |
|---|---|---|---|---|
| C-LOG-SEND | `_send_detection_request` log messages/extra-payload text (case, XX-clobber, None msg, exc_info removal counted separately) | 184 | EQUIVALENT | m97, m98, m100 |
| C-SPAN | telemetry span attrs / AIModelAttributes / set_detection_/set_inference_result attrs in send+segment (model_provider, device, batch_size, retry_attempt, status="success", inference_time_ms math feeding only span attrs, `detections = result.get("detections", [])` result-key mutants) | 102 | LOW-VALUE | send m6, send m7, seg m6 |
| C-METRIC | `record_pipeline_error` / `record_detection_by_class` / `observe_detection_confidence` label-text mutations | 72 | LOW-VALUE | det m29, det m30, send m122 |
| C-LOG-DET | `detect_objects` log message/extra text | 56 | EQUIVALENT | m18, m22, m154 |
| **C-BBOX** | `detect_objects` **bbox clamp / out-of-bounds geometry**: `>=`→`>` on image-size tests, `<=0`→`<0`/`<=1`, `or`→`and` in the 4-way outside-image disjunct, `max(0,..)`→`max(1,..)` clamps, `int(x2-x1)`→`int(x2+x1)`, `<1`→`<=1`/`<2` small-box tests, dims-guard `and`→`or`/`is`→`is not`, bbox-dict key set mutations | 40 | **TEST-GAP** | det m267, m282, m325 |
| C-WARMM | `warmup` metric labels ("yolo26","warm"/"cold") + completed-log text | 40 | LOW-VALUE | warmup m5, m9, m25 |
| C-EXCINFO | `exc_info=True`→False/None on error logs (traceback dropped) | 30 | LOW-VALUE | send m143, hc m19, det m418 |
| C-INITLOG | `__init__` log extra dict / `_model_version` / `_max_concurrent` (consumed only by log line) | 27 | LOW-VALUE | init m6, m110, m124 |
| C-LOG-VAL | `_validate_image_for_detection` log text | 27 | EQUIVALENT | m5, m9, m11 |
| C-LOG-HC | `health_check` log text (all 3 except branches) | 27 | EQUIVALENT | m7, m13, m27 |
| C-PROBE | `model_readiness_probe` test-image size/color + probe kwargs (mocked at `_send_detection_request` boundary; result ignored by design) | 24 | LOW-VALUE | m4, m10, m31 |
| **C-4XX** | `_send_detection_request` 4xx error-detail extraction: `if status_code == 400`→`!=`/`401`, `error_response.get("detail", str(e))` default/key mutants, raised ValueError message `{error_detail or e}`→`and e` — tests assert only that the list is empty, never the message/detail | 22 | **TEST-GAP** | m263, m264, m293 |
| **C-WARM** | warmth state machine: `get_warmth_state` `is None`→`is not None`, `>`→`>=` cold threshold, `"cold" if (is_cold) and False/or True`, string clobbers; `warmup` `_is_warming` set/reset (True→False start-state, finally `=True`), `was_cold=None`; `is_cold` `>`→`>=` boundary; `__init__` `_is_warming=False→True/None` | 16 | **TEST-GAP** | gws m1, gws m9, warmup m4/m61, init m105 |
| C-DUR | duration math (`-`→`+`, `*1000`→`/1000`/`*1001`) feeding only metrics/span/log | 16 | LOW-VALUE | send m61, det m452, seg m50 |
| **C-SEG-RT** | `segment_image` retry loop: `last_exception = e`→None, `attempt < max_retries-1` flips (`<=`,`+1`,`-2`), `delay=min(2**attempt,30)`→None/`2*attempt`/`3**attempt`/cap 31, `asyncio.sleep(delay)`→sleep(None), **`if status_code >= 500`→`> 500`/`>= 501` boundary**, `error_msg=None`, `original_error=None` | 16 | **TEST-GAP** | seg m75, m98, m116 |
| C-DEFALT | `detect_objects` missing class/bbox `.get(...)` default text/None ("unknown"→"UNKNOWN"/None, `bbox {}`→None) | 15 | LOW-VALUE | m212, m217, m227 |
| C-CBCFG | `__init__` CircuitBreakerConfig tuning (`failure_threshold` removed, `half_open_max_calls`/`success_threshold` None/+1) — open-threshold IS asserted (test_detector_client.py:1859); half-open/recovery tuning is not | 12 | LOW-VALUE | init m91, m94, m101 |
| **C-SEND-RT** | `_send_detection_request` backoff on branches with **no timing assertion**: `min(2**attempt,30)` cap→31 in TimeoutError/JSON/OSError handlers, `attempt < max_retries-1`→`<=`/`+1`/`-2` (OSError handler), `sleep(None)` — existing tests assert delays only for ConnectError/httpx-timeout/500 (test_detector_client.py:1437,1403,1468) | 11 | **TEST-GAP** | send m96, m306, m347 |
| **C-BASE** | `detect_objects` baseline update + session wiring: `session.add(None)`, `update_baseline(camera_id=.../detection_class=.../timestamp=...)` kwargs →None/removed, `detection.object_type is not None`→`is None` | 7 | **TEST-GAP** | m392, m440, m443 |
| **C-VIDEO** | `detect_objects` video branch: `video_path is not None and video_metadata is not None`→`or`, `file_type` default "video/mp4" text mutants, `is_video=False→True/None` | 10 | **TEST-GAP** | m174, m185, m199 |
| **C-SEG-PAY** | `segment_image` request payload: `files={"file":(name,data,"image/jpeg")}` key/mime mutants, `files=None`, `headers=self._get_auth_headers()`→None/removed — the only segment test asserts `"/segment" in url` | 9 | **TEST-GAP** | seg m37, m39, m44 |
| C-HTTPTO | `__init__` httpx.Timeout wiring →None/arg-removal (detect + health clients constructed but their timeout never exercised) | 9 | LOW-VALUE | init m41, m47, m74 |
| C-LIMITS | `httpx.Limits(max_connections=10, max_keepalive_connections=5)` tuning values | 7 | LOW-VALUE | init m78, m80, m83 |
| **C-SEND-PAY** | `_send_detection_request` multipart payload key/mime (`"file"`→"FILE"/clobber, `"image/jpeg"` case, `files=None`) + URL `f"{url}/detect"`→None — `httpx.AsyncClient.post` call args (url/files) are **never asserted anywhere** in test_detector_client.py | 8 | **TEST-GAP** | send m47, m48, m49 |
| C-SEG-LOG | `segment_image` log message text | 7 | EQUIVALENT | m62, m86, m92 |
| C-LOGCLOSE | `close()` log message text | 8 | EQUIVALENT | m1, m5, m7 |
| C-TIMEOUT | send/segment `explicit_timeout = read + connect` → None/subtraction and `asyncio.timeout(None)` — defense-in-depth disabled; the httpx-level timeout still fires under mocks, so behavior is indistinguishable in tests | 7 | LOW-VALUE | send m4, send m46, seg m35 |
| C-FREETHR | `_is_free_threaded` detection mutations (`hasattr(sys,...)`→None/case; `not` removed) — consumers are the dead preprocess executor + one log field | 4 | LOW-VALUE | m1, m6, m7 |
| **C-SEM** | `_get_semaphore` recreate condition `is None or != limit` flips (`and`, `is not`, `==`) — only `_semaphore_limit==4` after first call is asserted (test_detector_client.py:1328); identity/recreate-across-limit-change never asserted | 3 | **TEST-GAP** | m3, m4, m5 |
| **C-GW** | `__init__` gateway routing: `getattr(settings,"use_ai_gateway",False)` default→True/None, `gw_url.rstrip('/')` char clobber — gateway tests exercise only explicit True + clean URL | 3 | **TEST-GAP** | init m20, m26, m32 |
| **C-AUTH** | `_get_auth_headers` `hasattr(self._api_key,"get_secret_value")`→`hasattr(None,...)`/case/clobber — falls back to `str(SecretStr)` = masked repr; correlation test uses a plain **str** key so the SecretStr branch never discriminates | 3 | **TEST-GAP** | m4, m8, m9 |
| **C-CONFDEF** | `detect_objects` missing-confidence default `0.0`→**`1.0`**/None (`1.0` makes a detection with no confidence field pass every threshold) | 3 | **TEST-GAP** | m204, m206, m209 |
| **C-BRK** | per-detection `continue`→`break` (invalid detection silently drops the **rest of the batch** instead of just itself) | 3 | **TEST-GAP** | m244, m261, m422 |
| C-SEND-KW | `detect_objects` `_send_detection_request(image_name=image_file.name / image_path=... / camera_id=...)` kwargs→None (feeds payload only) | 5 | **TEST-GAP** | m114, m115, m116 |
| C-LOGSEM | `_get_semaphore` `logger.debug("Created new semaphore...")`→None (log text only; the recreate-condition mutants stay in C-SEM) | 1 | EQUIVALENT | m9 |
| C-PREPROC | `_get_preprocess_worker_count` `return 2`→3 — `_get_preprocess_executor` has **zero callers** repo-wide ⇒ dead code | 1 | EQUIVALENT | m1 |
| C-LASTEXC | send/segment `last_exception: Exception | None = None`→`""` — post-loop every except sets it, so falsy-vs-None is unreachable | 1 | EQUIVALENT | send m1 |
| **C-MINSZ** | `_validate_image_for_detection` `file_size < MIN_DETECTION_IMAGE_SIZE`→`<=` (an image exactly 10240 bytes flips valid→invalid); tests use sizes far from the boundary | 1 | **TEST-GAP** | m4 |
| C-ASVAL | async validate wrapper `camera_id`→None (log-context only) | 1 | EQUIVALENT | m3 |
| C-HURL | `health_check` URL→None (no assert; call still fails → False) | 1 | LOW-VALUE | m2 |

Totals: TEST-GAP 160, LOW-VALUE 366, EQUIVALENT 313 — sum 839 (40 clusters).

## Why the big clusters are not test gaps

- **C-LOG-* / C-SPAN / C-METRIC / C-DUR / C-EXCINFO / C-INITLOG / C-WARMM / C-DEFALT** (~460 of the 839):
  every mutation lands in `logger.*(message, extra=...)` text, Prometheus label strings, or OTel
  span-attribute values. No test (and arguably no test *should*) assert log/message text; the
  observable function contracts (return values, raised exceptions, DB writes) are unchanged.
  C-SPAN is LOW-VALUE rather than EQUIVALENT because the attributes are a real behavior surface,
  just one this codebase deliberately does not assert (NEM-3797 tests assert only
  `add_span_event` event names + camera.id — see test_detector_client.py:2175-2325).
- **C-PROBE**: the probe image is a sentinel; `model_readiness_probe` discards the inference
  result and only maps exception→False (test_model_warmup.py:271-294 patches
  `_send_detection_request`, so payload mutations cannot be observed at that boundary).
- **C-PREPROC / C-LASTEXC / C-ASVAL**: dead code / unreachable-state changes.

## Drafted tests for the 6 highest-value TEST-GAP clusters

> **UNVERIFIED - not yet run red/green** (task constraint: no test execution).
> TDD procedure for each: run the test against the mutant copy → expect FAIL (assert named below);
> run against original `backend/services/detector_client.py` → expect PASS.

### 1. C-BBOX (40 mutants) — `test_detect_objects_bbox_clamp_geometry`
Target: `backend/tests/unit/services/test_detector_client.py` (style: `test_detect_objects_stores_image_dimensions_for_bbox_scaling`, line 2328).
Kills m262/m263/m264 (dims-guard flips), m265-m267 (or→and), m268/m269/m271/m272/m274/m275 (boundary), m282/m292/m302/m313 (`max(0→1`), m325/m328 (`-`→`+`), m329-m333 (small-box), m232-m242 (bbox-dict keys).

```python
@pytest.mark.asyncio
async def test_detect_objects_bbox_clamp_geometry(detector_client, mock_session):
    """Exact clamped/skipped outcomes for the bbox geometry rules (WP4.4 mutant kill).

    image is 640x480; detections:
      A [100, 150, 300, 400]  -> in bounds, unchanged
      B [-10, 10, 50, 50]     -> clamped x to 0 (kills max(1,...))
      C [-100, 10, 101, 10]   -> x+w == 1 > 0 stays (kills <=0-><0 / <=1 and <1-><=1/<2 flips)
      D [640, 100, 50, 50]    -> x >= width: completely outside -> skipped
      E [100, 600, 50, 50]    -> y >= height: completely outside -> skipped
      F [100, 150, 600, 400]  -> clamped to (100,150,540,330) (kills x2_clamped + x1 flips)
    """
    image_path = "/export/foscam/front_door/geom.jpg"
    response = {
        "detections": [
            {"class": "person", "confidence": 0.95, "bbox": [100, 150, 300, 400]},
            {"class": "person", "confidence": 0.95, "bbox": [-10, 10, 50, 50]},
            {"class": "person", "confidence": 0.95, "bbox": [-100, 10, 101, 10]},
            {"class": "person", "confidence": 0.95, "bbox": [640, 100, 50, 50]},
            {"class": "person", "confidence": 0.95, "bbox": [100, 600, 50, 50]},
            {"class": "car", "confidence": 0.95, "bbox": [100, 150, 600, 400]},
        ],
        "image_width": 640,
        "image_height": 480,
    }
    with (
        patch("pathlib.Path.exists", return_value=True, autospec=True),
        patch("pathlib.Path.read_bytes", return_value=b"fake", autospec=True),
        patch("httpx.AsyncClient.post", autospec=True) as mock_post,
        patch.object(
            detector_client, "_validate_image_for_detection_async", return_value=True, autospec=True
        ),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response
        mock_post.return_value = mock_response

        detections = await detector_client.detect_objects(image_path, "front_door", mock_session)

    assert [(d.bbox_x, d.bbox_y, d.bbox_width, d.bbox_height) for d in detections] == [
        (100, 150, 300, 400),  # A untouched
        (0, 10, 40, 50),       # B clamped at 0
        (0, 10, 1, 10),        # C 1px sliver survives
        (100, 150, 540, 330),  # F clamped to image bounds (D, E dropped)
    ]


@pytest.mark.asyncio
async def test_detect_objects_partial_dimensions_skip_clamping(detector_client, mock_session):
    """width present but height absent -> clamp block is skipped entirely, raw bbox stored."""
    response = {
        "detections": [
            {"class": "car", "confidence": 0.95, "bbox": [100, 150, 600, 400]},
        ],
        "image_width": 640,
        # no image_height
    }
    with (
        patch("pathlib.Path.exists", return_value=True, autospec=True),
        patch("pathlib.Path.read_bytes", return_value=b"fake", autospec=True),
        patch("httpx.AsyncClient.post", autospec=True) as mock_post,
        patch.object(
            detector_client, "_validate_image_for_detection_async", return_value=True, autospec=True
        ),
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = response
        mock_post.return_value = mock_response

        detections = await detector_client.detect_objects(
            "/export/foscam/front_door/partial.jpg", "cam", mock_session
        )

    # and->or flip would enter the clamp block, hit min(150, None) TypeError and drop the detection
    assert len(detections) == 1
    assert (detections[0].bbox_x, detections[0].bbox_width) == (100, 600)
```

### 2. C-WARM (16 mutants) — warmth state machine
Target: `backend/tests/unit/services/test_model_warmup.py::TestDetectorClientWarmup`
(current coverage `test_get_warmth_state_returns_correct_structure`, line 340, accepts *any* of the
three strings — too weak to kill anything).
Kills get_warmth_state m1/m3/m4/m5/m8-m11, is_cold m5, warmup m4/m60/m61, __init__ m104/m105.

```python
    def test_get_warmth_state_warm_exact(self, detector_client, mock_settings):
        """Warm model reports 'warm' with measured seconds since last inference."""
        detector_client._is_warming = False
        detector_client._last_inference_time = time.monotonic() - 30

        state = detector_client.get_warmth_state()

        assert state["state"] == "warm"
        assert 29.0 < state["last_inference_seconds_ago"] < 40.0

    def test_get_warmth_state_cold_exact(self, detector_client, mock_settings):
        detector_client._is_warming = False
        detector_client._last_inference_time = time.monotonic() - 600  # threshold is 300

        state = detector_client.get_warmth_state()

        assert state["state"] == "cold"
        assert state["last_inference_seconds_ago"] > 590

    def test_is_cold_boundary_is_strict(self, detector_client):
        """Exactly at the threshold the model is still warm (comparison is strict >)."""
        threshold = detector_client._cold_start_threshold
        detector_client._last_inference_time = time.monotonic() - (threshold - 0.05)
        assert detector_client.is_cold() is False

    def test_warming_flag_overrides_and_resets(self, detector_client):
        detector_client._is_warming = True
        detector_client._last_inference_time = None
        assert detector_client.get_warmth_state()["state"] == "warming"

    @pytest.mark.asyncio
    async def test_warmup_sets_and_clears_is_warming(self, detector_client):
        """_is_warming is True *during* the probe and False after (finally clause)."""
        seen = {}

        async def probe_side_effect():
            seen["during"] = detector_client._is_warming
            return True

        with patch.object(
            detector_client, "model_readiness_probe", side_effect=probe_side_effect
        ):
            result = await detector_client.warmup()

        assert result is True
        assert seen["during"] is True
        assert detector_client._is_warming is False
```

### 3. C-SEG-RT (16 mutants) — segment retry semantics
Target: `backend/tests/unit/services/test_detector_client_segmentation.py::TestDetectorClientSegmentation`.
Kills m75/m76/m77 (attempt bound), m78/m83/m84/m85/m90 (delay math), m98/m99 (HTTP-500 boundary),
m101 (error_msg None), m116 (original_error dropped), m74 (last_exception dropped).

```python
    @pytest.mark.asyncio
    async def test_segment_image_500_is_retried_and_preserves_error(
        self, detector_client, mock_http_client
    ):
        """HTTP 500 (exactly) must be retried with backoff 1s,2s and preserved as original_error."""
        from backend.core.exceptions import DetectorUnavailableError

        def make_500(*args, **kwargs):
            response = MagicMock(spec=httpx.Response)
            response.status_code = 500
            raise httpx.HTTPStatusError(
                "Server Error", request=MagicMock(spec=httpx.Request), response=response
            )

        mock_http_client.post.side_effect = make_500

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(DetectorUnavailableError) as exc_info:
                await detector_client.segment_image(b"fake")

        # exactly max_retries attempts, exactly max_retries-1 backoff sleeps
        assert mock_http_client.post.call_count == 3
        assert [c[0][0] for c in mock_sleep.call_args_list] == [1, 2]
        assert isinstance(exc_info.value.original_error, httpx.HTTPStatusError)
        assert "failed after 3 attempts" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_segment_image_500_then_success(self, detector_client, mock_http_client):
        """Boundary: status_code == 500 takes the retry branch, not the 4xx ValueError branch."""
        ok = MagicMock()
        ok.json.return_value = {"detections": []}
        ok.raise_for_status = MagicMock()
        err500 = MagicMock(spec=httpx.Response)
        err500.status_code = 500
        mock_http_client.post.side_effect = [
            httpx.HTTPStatusError("err", request=MagicMock(), response=err500),
            ok,
        ]
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await detector_client.segment_image(b"fake")
        assert result == {"detections": []}
        assert mock_sleep.call_args_list[0][0][0] == 1  # 2**0, kills 2*attempt mutant
```

### 4. C-SEND-RT (11) + C-SEND-PAY (8) + C-SEND-KW (5, partial: m114/m116) — unasserted backoff branches and request payload
Target: `backend/tests/unit/services/test_detector_client.py` (style of `test_send_detection_request_connect_error_backoff_timing`, line 1437 — which asserts timing *only* for the ConnectError branch).
Kills send m96/m155/m217/m304/m305/m306 (backoff math on TimeoutError/5xx/JSON/OSError handlers), m328/m347-m349 (sleep(None), OSError attempt-bound flips), m47-m57/m64 (payload), det m114/m116 (image_name/image_path kwargs).

```python
@pytest.mark.asyncio
async def test_send_detection_request_payload_and_backoff_branches(mock_session):
    """Assert the /detect payload every send test ignores, and the backoff schedule on the
    asyncio-TimeoutError + OSError branches (existing timing tests cover only
    ConnectError/httpx-timeout/500)."""
    detector_client = DetectorClient(max_retries=7)
    image_path = "/export/foscam/front_door/payload.jpg"

    # --- payload shape on the success path (capture idiom from
    #     test_correlation_propagation.py::capture_post — autospec call_args would include self) ---
    captured = {}

    async def capture_post(*args, **kwargs):
        # autospec binding may or may not pass the client as args[0]; pick the first string
        captured["url"] = next((a for a in args if isinstance(a, str)), kwargs.get("url"))
        captured["files"] = kwargs.get("files")
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.return_value = {"detections": []}
        response.raise_for_status = MagicMock()
        return response

    with (
        patch("pathlib.Path.exists", return_value=True, autospec=True),
        patch("pathlib.Path.read_bytes", return_value=b"imgbytes", autospec=True),
        patch("httpx.AsyncClient.post", side_effect=capture_post, autospec=True),
        patch.object(
            detector_client, "_validate_image_for_detection_async", return_value=True, autospec=True
        ),
    ):
        await detector_client.detect_objects(image_path, "front_door", mock_session)

        assert captured["url"].endswith("/detect")
        assert captured["files"] == {"file": ("payload.jpg", b"imgbytes", "image/jpeg")}

    # --- asyncio.TimeoutError branch: full exponential schedule incl. 30s cap ---
    detector_client2 = DetectorClient(max_retries=7)
    with (
        patch("pathlib.Path.exists", return_value=True, autospec=True),
        patch("pathlib.Path.read_bytes", return_value=b"fake", autospec=True),
        patch("httpx.AsyncClient.post", side_effect=TimeoutError("asyncio"), autospec=True),
        patch.object(
            detector_client2, "_validate_image_for_detection_async", return_value=True, autospec=True
        ),
        patch("asyncio.sleep", new_callable=AsyncMock) as sleep_timeout,
    ):
        with pytest.raises(DetectorUnavailableError) as exc_info:
            await detector_client2.detect_objects(image_path, "front_door", mock_session)
        assert [c[0][0] for c in sleep_timeout.call_args_list] == [1, 2, 4, 8, 16, 30]
        assert isinstance(exc_info.value.original_error, TimeoutError)

    # --- OSError branch: same schedule, exactly max_retries-1 sleeps ---
    detector_client3 = DetectorClient(max_retries=7)
    with (
        patch("pathlib.Path.exists", return_value=True, autospec=True),
        patch("pathlib.Path.read_bytes", return_value=b"fake", autospec=True),
        patch("httpx.AsyncClient.post", side_effect=OSError("disk"), autospec=True),
        patch.object(
            detector_client3, "_validate_image_for_detection_async", return_value=True, autospec=True
        ),
        patch("asyncio.sleep", new_callable=AsyncMock) as sleep_os,
    ):
        with pytest.raises(DetectorUnavailableError) as exc_info:
            await detector_client3.detect_objects(image_path, "front_door", mock_session)
        assert [c[0][0] for c in sleep_os.call_args_list] == [1, 2, 4, 8, 16, 30]
        assert isinstance(exc_info.value.original_error, OSError)
```

### 5. C-SEG-PAY (9) — segment request payload + auth header
Target: `backend/tests/unit/services/test_detector_client_segmentation.py`.
Kills seg m36-m47 (files key/mime, files=None, headers=None/removed).

```python
    @pytest.mark.asyncio
    async def test_segment_image_sends_multipart_payload_and_auth_header(
        self, detector_client, mock_http_client
    ):
        mock_response = MagicMock()
        mock_response.json.return_value = {"detections": []}
        mock_response.raise_for_status = MagicMock()
        mock_http_client.post.return_value = mock_response

        detector_client._api_key = "segment-secret"
        await detector_client.segment_image(b"segbytes", image_name="frame7.jpg")

        call = mock_http_client.post.call_args
        assert call[0][0].endswith("/segment")
        assert call[1]["files"] == {"file": ("frame7.jpg", b"segbytes", "image/jpeg")}
        assert call[1]["headers"].get("X-API-Key") == "segment-secret"
```

### 6. C-AUTH (3) — SecretStr branch of `_get_auth_headers`
Target: `backend/tests/unit/services/test_detector_client.py`. Existing header test
(test_correlation_propagation.py:233) uses a plain str key, so the `hasattr(..., "get_secret_value")`
branch is never discriminated — `hasattr(None, ...)` mutants fall through to the *masked* str().

```python
def test_get_auth_headers_unwraps_secretstr_key():
    """SecretStr keys must be unwrapped via get_secret_value(), not str()-masked."""
    from pydantic import SecretStr

    with patch("backend.services.detector_client.get_settings") as mock_get_settings:
        settings = MagicMock()
        settings.yolo26_url = "http://localhost:8095"
        settings.yolo26_api_key = SecretStr("super-secret")
        mock_get_settings.return_value = settings
        client = DetectorClient(max_retries=1)

    headers = client._get_auth_headers()

    assert headers["X-API-Key"] == "super-secret"
    assert "secret*" not in headers["X-API-Key"].lower()  # str(SecretStr) masks the value
```

## Remaining TEST-GAP clusters worth a follow-up pass (not drafted)

- **C-4XX (22)** — `_send_detection_request` raises `ValueError(f"Detector client error {code}: {detail}")`; a direct unit test on `_send_detection_request` asserting the message contains the 400 JSON `detail` kills m263-m274/m293. Existing test test_detector_client.py:899 only asserts the empty return.
- **C-BASE (7)** — assert `update_baseline` called with `camera_id`/`detection_class`/`timestamp` kwargs and `session.add` receives `Detection` instances (`mock_session.add.call_args[0][0].object_type == "person"`). Mock baseline service exists already (fixture line 16).
- **C-VIDEO (10)** — pass `video_path` with `video_metadata=None` (and vice versa) and assert the image branch is taken (kills `and`→`or` at m174); assert stored `file_type == "video/mp4"` default.
- **C-SEM (3)** — assert `DetectorClient._get_semaphore()` identity is stable across calls, and *changes* when `settings.ai_max_concurrent_inferences` changes (kills `==`/`and`/`is not` flips; the 4th original member, the `logger.debug`→None mutant, was reclassified EQUIVALENT as C-LOGSEM in the final pass).
- **C-SEND-KW (5)** — `_send_detection_request` kwargs `image_name`/`image_path`/`camera_id`→None: assert the call kwargs once (`assert_called_once` with expected kwargs, or inspect `call_args.kwargs`) — pairs naturally with the payload test drafted above.
- **C-BRK (3)** — response with [bad-bbox detection, good detection] must still store the good one (kills `continue`→`break`).
- **C-CONFDEF (3)** — detection without a `confidence` key must be filtered (default 0.0), not stored (m209 default→1.0).
- **C-MINSZ (1)** — file sized exactly `MIN_DETECTION_IMAGE_SIZE` (10240 B) must validate.
- **C-GW (3)** — settings object lacking `use_ai_gateway` must NOT route through gateway (kills default→True); `ai_gateway_url="http://gw:8000/"` (trailing slash) must produce `"http://gw:8000/yolo26"`.

## Notes for WP4.4

- The `ǁ`-mangled mutant keys are unresolvable by `mutmut show` (FileNotFoundError in
  `find_mutant`) — dossier diffs come from the spans file; WP4.4 tooling should reuse the
  span-diff path, not `mutmut show`.
- `test_model_warmup.py::TestDetectorClientWarmup::test_get_warmth_state_returns_correct_structure`
  is the archetypal weak assertion in this module (accepts any of 3 states); strengthening it is
  the single cheapest kill-rate win (cluster C-WARM).
- ~55% of survivors (C-LOG-*/C-SPAN/C-METRIC) are log/telemetry text. If the team wants a higher
  baseline kill ratio without new tests, that is a mutation-config conversation (skip logging
  statements), not a test-gap one.

Generated 2026-09-18 by WP4.3 triage (detector_client). All draft tests UNVERIFIED.
