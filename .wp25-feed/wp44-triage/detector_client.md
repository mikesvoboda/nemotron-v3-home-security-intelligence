# WP4.4 Triage Dossier — backend/services/detector_client.py

**Run snapshot (this session):** 1376 mutant keys in `mutants/backend/services/detector_client.py.meta` —
**167 survived (exit 0)**, 30 killed (exit 1), 42 timeout (exit -24), 1137 unchecked (null).
The live `mutmut run --max-children 12` (started 14:15) is still checking; all 167 survivors so far live in
five functions: `segment_image` 89, `warmup` 45, `model_readiness_probe` 24, `get_warmth_state` 8, `is_cold` 1.

**Diff source:** the on-disk mutant copy was COLLAPSED to byte-identity with the source mid-session
(the 14:15 rerun's rewrite raced generation). After the live run re-expanded the copy (14:25, 19MB,
2786 `__mutmut_` names) `uv run mutmut show <key>` worked for **all 167** survivors — no manual diffing,
no numbering guesswork. Raw per-key diffs: `/tmp/wp25/wp44-triage/dc-diffs/<key>.diff` (167 files);
compact change summary: `/tmp/wp25/wp44-triage/dc_changes.json`. Meta snapshot: `dc-meta-snapshot.json`.

**Cluster census:** 29 clusters, counts sum to **167** = TEST-GAP 74 + LOW-VALUE 58 + EQUIVALENT 35.
(Partition validated programmatically against `dc_changes.json`: no dupes, no orphans.)

## Covering tests (from `mutants/mutmut-stats.json` → tests_by_mangled_function_name)

| Function | Covering test(s) | file:line |
|---|---|---|
| `get_warmth_state` | `TestDetectorClientWarmup::test_get_warmth_state_returns_correct_structure` | `backend/tests/unit/services/test_model_warmup.py:340` |
| `is_cold` | `test_is_cold_when_never_used` :322, `test_is_cold_after_threshold_exceeded` :328, `test_is_warm_within_threshold` :334, `test_warmup_failure` :311, `test_warmup_with_test_image_success` :297 | same file |
| `model_readiness_probe` | `test_model_readiness_probe_success` :271, `test_model_readiness_probe_failure` :283 | same file |
| `warmup` | `test_warmup_with_test_image_success` :297, `test_warmup_failure` :311 | same file |
| `segment_image` | 6 tests in `TestDetectorClientSegmentation` (`test_segment_image_success` :37, `_calls_segment_endpoint` :70, `_retries_on_connection_error` :84, `_raises_on_all_retries_exhausted` :106, `_raises_value_error_on_4xx` :120, `_empty_detections` :133) | `backend/tests/unit/services/test_detector_client_segmentation.py` |

**Why so much survives (verified in the test sources):**
- `test_model_readiness_probe_success` patches `_send_detection_request` bare `AsyncMock` and asserts only
  `result is True` — every probe kwarg (`image_data`, `image_name`, `camera_id`, `image_path`) and the
  generated image's shape/color/format are never inspected.
- `test_warmup_*` patch `model_readiness_probe` and assert only the return bool + `_last_inference_time`.
  The `set_model_warmth_state` / `observe_model_warmup_duration` / `record_model_cold_start` calls (labels
  `"yolo26"`, states `"warming"/"warm"/"cold"`) are never observed.
- `test_get_warmth_state_returns_correct_structure` asserts only key presence and
  `state in ("cold","warm","warming")` — a membership assert, so case/mark variants pass and the
  cold↔warm branch flip only passes when it lands inside the allowed set. `last_inference_seconds_ago`
  value never checked (Nemotron's twin test at :177 checks `< 60`; DetectorClient's does not).
- `segment_image` tests mock `_get_semaphore` + `_http_client`, patch `asyncio.sleep` BARE, and never assert:
  the multipart `files` dict, the `headers` kwarg, sleep *delays* or *counts*, `original_error`, the error
  message, `record_pipeline_error` labels, or status-500 retry behavior (existing tests use 400/ConnectError only).

**Facts used in classification (verified against source / PIL / httpx this session):**
- PIL `Image.new("RGB", (32, 32))` without `color=` defaults to black — omitting the kwarg is equivalent.
- PIL JPEG save is format-case-insensitive — `"jpeg"` == `"JPEG"` output → equivalent.
- `"XXliteralXX"` / `"UPPERCASE"` string mutants: no consumer parses these fields (metrics labels, span
  attributes, log text, `/dev/null` placeholder path never opened — `_send_detection_request` is mocked in
  every covering test; segment path goes to a mocked httpx post) → EQUIVALENT.
- `Exception | None = ""` vs `= None`: both falsy, overwritten in every except path, guard is `if last_exception:`
  → EQUIVALENT.
- `if isinstance(...)`-free booleans: `_is_warming = None` is falsy ≡ `False` for the `if self._is_warming:`
  consumer (only killable by a strict `is False` identity assert) → EQUIVALENT (behavior-preserving).
- Backoff `min(2**attempt, 30)`: for attempts 0..4 (any r ≤ 6) `2**attempt ≤ 16 < 30`, so the 30→31 cap
  mutation is only killable with `max_retries ≥ 10` (attempt 5..8 sleeps: 30 vs 31). Drafted T5 uses r=10.
- `metrics` are function-local imports in `warmup` (`from backend.core.metrics import ...` at
  detector_client.py:556) → patch targets are `backend.core.metrics.<fn>`.
- `DetectorUnavailableError.original_error` stored verbatim (`backend/core/exceptions.py:395`).

## Cluster table (key numbers are `__mutmut_N` within the function)

### `get_warmth_state` (8 survivors)

| # | Cluster | N | Keys | Class | Note / kill vector |
|---|---|---|---|---|---|
| G-A | warm/cold decision flipped or short-circuited: `is None`→`is not None`; `is_cold = None`; `if (is_cold) and False`; `if (is_cold) or True` | 4 | 1, 4, 8, 9 | **TEST-GAP** | Structure test's membership assert can't see a wrong-but-valid state. T-G3 below (tighten :340). |
| G-B | `seconds_ago = monotonic() - t` → `+` | 1 | 3 | LOW-VALUE | Only poisons `last_inference_seconds_ago` numeric value; `state` key unaffected. Killable only by value assert (T-G3 would incidentally kill). |
| G-C | cold threshold `>` → `>=` | 1 | 5 | LOW-VALUE | Single-point boundary; no test sits exactly at threshold. |
| G-D | `"cold"` → `"XXcoldXX"` / `"COLD"` | 2 | 10, 11 | EQUIVALENT | Membership assert passes; no consumer compares exact string within this method's outputs. |

Kill vector for G-A/G-B (`test_model_warmup.py::TestDetectorClientWarmup`, extend the :340 test or add):
set `_last_inference_time = monotonic() - 600` → `state == "cold"` and
`599 < last_inference_seconds_ago < 601`; set `- 60` → `state == "warm"`; set `_is_warming=True` → `"warming"`.

### `is_cold` (1)

| # | Cluster | N | Keys | Class | Note |
|---|---|---|---|---|---|
| I-A | `seconds_since_last > threshold` → `>=` | 1 | 5 | LOW-VALUE | Same single-point boundary as G-C (fixture uses 60s/600s vs 300s threshold, never ==300). |

### `model_readiness_probe` (24)

| # | Cluster | N | Keys | Class | Note / kill vector |
|---|---|---|---|---|---|
| P-A | test-image geometry/color mutated: `(32,32)`→`(33,32)`/`(32,33)`; `color=(0,0,0)`→`(1,0,0)`/`(0,1,0)`/`(0,0,1)` | 5 | 10, 11, 12, 13, 14 | **TEST-GAP** | T1 decodes the sent JPEG and asserts 32×32 black. |
| P-B | probe call kwargs dropped/None'd: `image_data=None` (assign + kwarg), `image_name`, `camera_id`, `image_path` → None/dropped | 9 | 22, 23, 24, 25, 26, 27, 28, 29, 30 | **TEST-GAP** | T1 asserts the exact kwargs on the `_send_detection_request` mock. |
| P-D | string case/mark mutations of `image_name`/`camera_id`/`image_path` literals | 6 | 31–36 | EQUIVALENT | Names never asserted; `/dev/null` path never opened (send is mocked). |
| P-E | `logger.warning(f"...{e}")` → `logger.warning(None)` | 1 | 38 | EQUIVALENT | Log text only; exception still swallowed → False. |
| P-F | `color=None` / `color=` kwarg dropped / `format="jpeg"` | 3 | 4, 7, 21 | EQUIVALENT | **Verified on Pillow 12.3.0 (this env):** `Image.new(..., color=None)` yields pixel `(0,0,0)` — identical to black; omitting `color=` is PIL's black default; `"jpeg"` and `"JPEG"` emit byte-identical JPEG bytes. |

### `segment_image` (89)

| # | Cluster | N | Keys | Class | Note / kill vector |
|---|---|---|---|---|---|
| S-A | `last_exception = None` init → `""` | 1 | 1 | EQUIVALENT | Falsy-init only. |
| S-B | timeout composition: `+`→`None`/`-`; `asyncio.timeout(explicit_timeout)`→`timeout(None)` | 3 | 4, 5, 35 | **TEST-GAP** | No test bounds the request deadline. Kill vector (not drafted): monkeypatch `asyncio.timeout` wrapper capturing the arg; assert `== client._read_timeout + settings.ai_connect_timeout`; `timeout(None)` waits forever → hang/`pytest-timeout` red. |
| S-C | trace-span plumbing: span name → None, `image_size_bytes` None/dropped (#9 drops the `image_size_bytes=` kwarg from `trace_span`), `AIModelAttributes.set_on_span` kwargs → None/dropped | 13 | 6, 7, 9, 11, 12, 13, 14, 15, 17, 18, 19, 20, 21 | LOW-VALUE | Telemetry attributes; behavior identical. Tests would only be worth it if a trace-contract test class existed. |
| S-D | telemetry label case/mark (`"huggingface"`, `"cuda:0"`, `batch_size=1→2`) | 5 | 22–26 | EQUIVALENT | OTel attribute values, no reader. |
| S-E | `span.set_attribute("retry_attempt", …)` key/value mutations | 4 | 28, 29, 32, 33 | LOW-VALUE | Span attribute only. |
| S-F | observability payload mutations: `inference_time_ms=None`, `detections` key case/mark, `set_detection_attributes`/`set_inference_result_attributes` kwarg None/drop, `status` case | 14 | 49, 53, 58, 59, 61, 62, 64, 65, 67, 68, 70, 71, 72, 73 | LOW-VALUE | Span/metrics payload; returned dict untouched (`result` returned as-is). |
| S-G | multipart payload mutated at the httpx boundary: `files=None` (assign + kwarg + drop), `headers=None`/dropped, dict key `"file"`→`"XXfileXX"`/`"FILE"`, MIME `"image/jpeg"`→`"XXimage/jpegXX"`/`"IMAGE/JPEG"` | 9 | 36, 37, 38, 39, 40, 43, 44, 46, 47 | **TEST-GAP** | T4 asserts `post` kwargs `files == {"file": (name, bytes, "image/jpeg")}` and `headers == _get_auth_headers()`. |
| S-H | `inference_time_ms` arithmetic (`*1000`→`/1000`, `+start_time`, `*1001`, None) | 3 | 50, 51, 52 | LOW-VALUE | Feeds only span duration attrs. |
| S-I | `result.get("detections", …)` key/None-default mutations | 3 | 54, 55, 57 | LOW-VALUE | Value feeds only `set_detection_attributes`; return payload unaffected. |
| S-Ja | retry machinery: `last_exception=e`→None; retry gate `<`→`<=`/`+1`/`-2`; `delay=None`, `2**`→`2*`, `2`→`3`, cap 30→31; `sleep(delay)`→`sleep(None)`; `record_pipeline_error` label→None | 10 | 74, 75, 76, 77, 78, 83, 84, 85, 90, 91 | **TEST-GAP** | Existing retry test patches `asyncio.sleep` BARE and only counts post calls; the settings fixture (`detector_max_retries=1`) never exercises backoff. T5 asserts post-call count + full sleep-delay sequence at r=10 (kills 75–78, 83–85, 90); T6 asserts `record_pipeline_error("yolo26_segmentation_error")` (91) and `original_error is conn_err` (74). |
| S-Jb | retry-path LOG text only: warning message→None, `attempt+1`→`attempt±1`, `sanitize_error(e)`→None, final-error log msg→None, `exc_info=True`→None/False | 8 | 86, 87, 88, 89, 92, 93, 95, 96 | LOW-VALUE | Real string/kwargs changes on the warning/error calls; no observable behavior (all paths still raise/return identically). Would need a `caplog`/logging-args contract test; noted, not drafted. |
| S-K | 5xx boundary `>= 500` → `> 500` / `>= 501` | 2 | 98, 99 | **TEST-GAP** | No test uses a 500/501 status; mutants silently reroute 500→ValueError (fast-fail instead of retry). T6b (500 + 501 cases) kills both. |
| S-L | final error payload: message `None`/dropped/default, `original_error=None`/dropped | 5 | 101, 115, 116, 117, 118 | **TEST-GAP** | Exhaustion test asserts only exception class. T6 asserts message match + `exc.original_error is conn_err`. |
| S-M | error span attributes (`"error"`, `"error.message"` key/value mutations) | 9 | 102, 103, 106, 107, 108, 109, 110, 113, 114 | LOW-VALUE | Telemetry only. |

### `warmup` (45)

| # | Cluster | N | Keys | Class | Note / kill vector |
|---|---|---|---|---|---|
| W-A | warming-flag lifecycle + `was_cold`: `_is_warming=True`→`False` (during); `finally False`→`True` (after); `was_cold=is_cold()`→`None` (suppresses cold-start metric) | 3 | 4, 61, 2 | **TEST-GAP** | T3: probe spy reads `get_warmth_state()` mid-warmup (→"warming") + `assert client._is_warming is False` after; T2 asserts `record_model_cold_start("yolo26")` fires. |
| W-B | metric/state call labels & state strings: `set_model_warmth_state`/`observe_model_warmup_duration`/`record_model_cold_start` model→None/`"XXyolo26XX"`/`"YOLO26"`; state→None/`"XXwarmingXX"`/`"WARMING"`/`"XXwarmXX"`/`"WARM"`/`"XXcoldXX"`/`"COLD"` | 24 | 5, 6, 9, 10, 11, 12, 21, 25, 26, 27, 28, 29, 30, 31, 34, 35, 36, 37, 47, 48, 51, 52, 53, 54 | **TEST-GAP** | T2 patches `backend.core.metrics.*` and asserts exact call sequence `("yolo26","warming") → ("yolo26","warm")` + label `"yolo26"` on duration/cold-start; failure path (probe→False) asserts final `("yolo26","cold")`. These are the Prometheus dimensions the ops dashboards key on. |
| W-C | log message text/`extra` payload mutations (`logger.info`/`logger.warning` None/case; `extra={"duration","was_cold"}` key mutations) | 15 | 13, 14, 15, 16, 38, 39, 41, 42, 43, 44, 45, 55, 56, 57, 58 | EQUIVALENT | Log text only; no behavior consumer. |
| W-D | `duration = monotonic() - start_time` → `+` | 1 | 20 | LOW-VALUE | Poisoned duration only reaches the metrics histogram; T2's `0 <= duration < 60` bound kills it incidentally. |
| W-E | `_is_warming` assign → `None` (before / in finally) | 2 | 3, 60 | EQUIVALENT | `None` falsy ≡ `False` for the only consumer (`if self._is_warming:`); T3's strict `is False` would kill via identity, semantically inert. |

## Drafted tests (UNVERIFIED — not run red/green; no test execution permitted this session)

TDD procedure (same for all): apply the drafted test, run the covering file → green on original
`backend/services/detector_client.py`; activate the cluster's mutant (mutmut trampoline / one-line swap
from `dc-diffs/`) → the listed assertion fails (red). Then green the whole file again.

### T1 — probe payload + image shape → kills P-A (5) + P-B (9)
File: `backend/tests/unit/services/test_model_warmup.py` (add `import io` at top; add to
`TestDetectorClientWarmup`; reuses its `detector_client` fixture at :259):

```python
    @pytest.mark.asyncio
    async def test_model_readiness_probe_sends_warmup_image_payload(self, detector_client):
        """Probe must upload a 32x32 black JPEG as warmup_test.jpg via the warmup camera."""
        import io

        from PIL import Image

        with patch.object(
            detector_client, "_send_detection_request", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = {"detections": []}

            result = await detector_client.model_readiness_probe()

        assert result is True
        kwargs = mock_send.call_args.kwargs
        assert kwargs["image_name"] == "warmup_test.jpg"
        assert kwargs["camera_id"] == "warmup"
        assert kwargs["image_path"] == "/dev/null"
        assert isinstance(kwargs["image_data"], bytes)
        assert kwargs["image_data"][:2] == b"\xff\xd8"  # JPEG magic

        sent_image = Image.open(io.BytesIO(kwargs["image_data"]))
        assert sent_image.size == (32, 32)
        assert sent_image.convert("RGB").getpixel((16, 16)) == (0, 0, 0)
```
Red behavior: every P-A/P-B key either changes a `call_args.kwargs` value, drops a key (KeyError), or
makes `Image.new`/probe raise so `result is True` fails / `call_args` is None.

### T2 — warmup metric labels + state sequence → kills W-B (24, +W-D incidentally)
Same file/class:

```python
    @pytest.mark.asyncio
    async def test_warmup_records_metric_labels_and_warmth_states(self, detector_client):
        """Success path must emit warming->warm with the exact 'yolo26' label."""
        with (
            patch.object(
                detector_client,
                "model_readiness_probe",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("backend.core.metrics.observe_model_warmup_duration") as mock_duration,
            patch("backend.core.metrics.record_model_cold_start") as mock_cold,
            patch("backend.core.metrics.set_model_warmth_state") as mock_state,
        ):
            result = await detector_client.warmup()

        assert result is True
        assert [c.args for c in mock_state.call_args_list] == [
            ("yolo26", "warming"),
            ("yolo26", "warm"),
        ]
        mock_cold.assert_called_once_with("yolo26")
        name, duration = mock_duration.call_args.args
        assert name == "yolo26"
        assert 0 <= duration < 60

    @pytest.mark.asyncio
    async def test_warmup_failure_sets_cold_state(self, detector_client):
        """Failed warmup must set (yolo26, cold), not a mutated label."""
        with (
            patch.object(
                detector_client,
                "model_readiness_probe",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("backend.core.metrics.set_model_warmth_state") as mock_state,
        ):
            result = await detector_client.warmup()

        assert result is False
        assert [c.args for c in mock_state.call_args_list] == [
            ("yolo26", "warming"),
            ("yolo26", "cold"),
        ]
```
(warmup re-imports the metric fns per call at detector_client.py:556, so patching
`backend.core.metrics.*` is the correct target.)

### T3 — warming-flag lifecycle → kills W-A #4/#61 (W-A #2 by T2)
Same file/class:

```python
    @pytest.mark.asyncio
    async def test_warmup_sets_warming_flag_only_during_probe(self, detector_client):
        """_is_warming is True only while the probe runs; warm afterwards."""
        seen = {}

        async def probe_spy():
            seen["during"] = detector_client.get_warmth_state()["state"]
            return True

        with patch.object(detector_client, "model_readiness_probe", side_effect=probe_spy):
            result = await detector_client.warmup()

        assert result is True
        assert seen["during"] == "warming"           # kills _is_warming=False-at-start (#4)
        assert detector_client._is_warming is False  # kills finally=True (#61), strict-identity also kills #3/#60
```

### T4 — segment multipart payload + headers → kills S-G (9)
File: `backend/tests/unit/services/test_detector_client_segmentation.py` (class
`TestDetectorClientSegmentation`, reuses its fixtures):

```python
    @pytest.mark.asyncio
    async def test_segment_image_sends_multipart_payload_and_headers(
        self, detector_client, mock_http_client
    ):
        """The POST must carry the file part under 'file' and the auth headers."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"detections": []}
        mock_response.raise_for_status = MagicMock()
        mock_http_client.post.return_value = mock_response

        with patch.object(
            DetectorClient, "_get_auth_headers", return_value={"X-API-Key": "k"}
        ):
            await detector_client.segment_image(b"segment_me", image_name="frame.jpg")

        args, kwargs = mock_http_client.post.call_args
        assert args[0].endswith("/segment")
        assert kwargs["files"]["file"] == ("frame.jpg", b"segment_me", "image/jpeg")
        assert kwargs["headers"] == {"X-API-Key": "k"}
```
Red: `files=None`/dropped, `headers=None`/dropped fail the kwargs asserts (KeyError counts as red).

### T5 — retry backoff sequence + attempt count → kills S-Ja gate/delay keys (8 of 10: 75–78, 83–85, 90)
Same file/class (add `from backend.core.exceptions import DetectorUnavailableError` at top):

```python
    @pytest.mark.asyncio
    async def test_segment_image_backoff_sequence_and_attempt_count(
        self, detector_client, mock_http_client
    ):
        """r retries => exactly r posts, r-1 sleeps, exponential delays capped at 30."""
        detector_client._max_retries = 10
        mock_http_client.post.side_effect = httpx.ConnectError("boom")

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(DetectorUnavailableError):
                await detector_client.segment_image(b"x")

        assert mock_http_client.post.call_count == 10
        assert [c.args[0] for c in mock_sleep.call_args_list] == [
            1, 2, 4, 8, 16, 30, 30, 30, 30
        ]
```
Red: gate mutations change sleep count (10 or 8); `delay=None`/`sleep(None)`/`2*attempt`/`3**attempt`/
cap 31 change the delay list. (Cap mutation #85 needs r>=10 — hence 10.)

### T6 — exhaustion payload + 5xx routing → kills S-L (5), S-K (2), S-Ja remainder (74, 91)
Same file/class:

```python
    @pytest.mark.asyncio
    async def test_segment_image_exhaustion_error_payload(self, detector_client, mock_http_client):
        """Exhausted retries must report the attempt count and chain the original error."""
        detector_client._max_retries = 1
        conn_err = httpx.ConnectError("connection refused")
        mock_http_client.post.side_effect = conn_err

        with (
            patch("backend.services.detector_client.record_pipeline_error") as mock_metric,
            pytest.raises(DetectorUnavailableError, match="failed after 1 attempts") as ei,
        ):
            await detector_client.segment_image(b"x")

        assert ei.value.original_error is conn_err
        mock_metric.assert_called_once_with("yolo26_segmentation_error")

    @pytest.mark.asyncio
    async def test_segment_image_retries_500_and_marks_server_error(
        self, detector_client, mock_http_client
    ):
        """HTTP 500 must RETRY (not fast-fail as ValueError) and mark server-error metric."""
        detector_client._max_retries = 2
        resp = MagicMock()
        resp.status_code = 500
        mock_http_client.post.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=resp
        )

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("backend.services.detector_client.record_pipeline_error") as mock_metric,
            pytest.raises(DetectorUnavailableError),
        ):
            await detector_client.segment_image(b"x")

        assert mock_http_client.post.call_count == 2
        mock_metric.assert_called_once_with("yolo26_segmentation_server_error")

    @pytest.mark.asyncio
    async def test_segment_image_retries_501(self, detector_client, mock_http_client):
        """HTTP 501 must also take the retry path (>= 500 boundary)."""
        detector_client._max_retries = 2
        resp = MagicMock()
        resp.status_code = 501
        mock_http_client.post.side_effect = httpx.HTTPStatusError(
            "Not Implemented", request=MagicMock(), response=resp
        )

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(DetectorUnavailableError),
        ):
            await detector_client.segment_image(b"x")

        assert mock_http_client.post.call_count == 2
```
Red: `>=500`→`>500`/`>=501` reroute these statuses into `raise ValueError` → wrong exception type fails
`pytest.raises(DetectorUnavailableError)`.

### T-G3 (small, not counted in the six above) — warmth-state exactness → kills G-A (4, +G-B)
Extend `test_get_warmth_state_returns_correct_structure` (test_model_warmup.py:340):
after `state = detector_client.get_warmth_state()` add
`assert state["state"] == "warm"` and `assert 29 < state["last_inference_seconds_ago"] < 31`;
then also set `_last_inference_time = time.monotonic() - 600` and assert `state == {"state": "cold", ...}`
exact key; `_is_warming=True` → `"warming"`.

## Verification queue for the serial pytest lane (WP4.4)
1. `test_model_warmup.py` T1–T3 + T-G3 → expect red on mutants {P-A,P-B,W-A,W-B,G-A[,G-B]}, green on original.
2. `test_detector_client_segmentation.py` T4–T6 → expect red on all of {S-G (9), S-K (2), S-L (5), S-Ja (10)}, green on original. S-Jb (8 log-text keys) stays surviving by design — log-plumbing tail.
3. Note for the ledger: T5's r=10 run costs 10 mocked posts — <100ms; no timing flake risk
   (delays are asserted from patched `asyncio.sleep`, never slept).

## Raw evidence
- Per-mutant diffs: `/tmp/wp25/wp44-triage/dc-diffs/` (167 files, `mutmut show` output)
- Change summary JSON: `/tmp/wp25/wp44-triage/dc_changes.json`
- Meta snapshot at triage time: `/tmp/wp25/wp44-triage/dc-meta-snapshot.json`
