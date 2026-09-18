# WP4.4 Triage Dossier — backend/services/clip_client.py

Generated: 2026-09-17 (WP4.3 finding feed → WP4.4). READ-ONLY triage; no tests executed, no repo files modified.

- Meta: `mutants/backend/services/clip_client.py.meta` → 1045 keys, 126 killed, 699 untested (not yet checked), **220 SURVIVED** (exit_code == 0).
- All 220 survivors sit in exactly two functions: `CLIPClient.anomaly_score` (109) and `CLIPClient.similarity` (111). The other methods (`embed`, `classify`, `batch_similarity`, ctor, helpers) have zero survivors — their tests are already tight.
- Diffs extracted offline: spans (`clip_client.py.spans`) → line-range diff of each `__mutmut_N` clobber vs its `__mutmut_orig` in the mutant copy. Keys below are shortened from `backend.services.clip_client.xǁCLIPClientǁ<FN>__mutmut_N` to `<FN>__mutmut_N`.
- Cluster counts below are produced by a single-pass, mutually-exclusive bucket over the changed line text: **sum = 220 exactly**.

## Covering tests (from mutants/mutmut-stats.json tests_by_mangled_function_name)

All in `backend/tests/unit/services/test_clip_client.py`:

| Concern | Location |
|---|---|
| `anomaly_score` happy + all 5 error paths | `TestAnomalyScore` :556 (success :560, connect :656, timeout :679, server :702 [status **503**], client :731 [**422**], unexpected :760, reraise :783) |
| `similarity` happy + all 5 error paths | `TestSimilarity` :1051 (success :1055, missing-field :1079, connect :1106, timeout :1128, server :1150 [status **502**], client :1176 [**404**], unexpected :1202, reraise :1224) |
| URL-only request assertions | `TestEdgeCases.test_anomaly_score_verifies_url_endpoint` :1584, `test_similarity_verifies_url_endpoint` :1634 — assert `call_args[0][0]` (URL) and nothing else about `json=`/`headers=` |
| Payload-shape assertion exists **only for embed** | `test_embed_sends_correct_payload` :1682 — anomaly/similarity have no equivalent |
| Breaker "all methods" test | `TestCircuitBreakerIntegration.test_circuit_breaker_affects_all_methods` :1890 — **passes for the wrong reason**: after opening the *embed* breaker it expects `CLIPUnavailableError` from every method, but with per-endpoint breakers intact those methods still issue the POST, whose mocked `ConnectError` gets wrapped into the same exception type. Breaker-label mutants pass by taking the *intended* (embed breaker) path instead — undetectable either way. |
| `original_error` constructor coverage (class only, not call sites) | `backend/tests/unit/core/test_exceptions.py` :415 |

Why anomaly_score raise-message mutants died but similarity's lived: `TestAnomalyScore` asserts message substrings (`"server error: 503"` etc.), `TestSimilarity` asserts only exception *type* + the `record_pipeline_error` label.

## Cluster table (sums to 220)

| # | Pattern (same change, same concern) | Count | Classification | Example keys (≤3) |
|---|---|---|---|---|
| 1 | Log message text replaced (debug/warning/error f-string → `None` / `XX…XX` / case-flip) — output text only | 25 | **EQUIVALENT** | anomaly_score__mutmut_11, anomaly_score__mutmut_42, similarity__mutmut_56 |
| 2 | Exception message cosmetic: case/`XX` wrapping of the "Malformed response…" strings (asserted substring preserved), or `sanitize_error(e)`→`sanitize_error(None)` inside the message | 8 | **EQUIVALENT** | anomaly_score__mutmut_47, similarity__mutmut_45, similarity__mutmut_165 |
| 3 | `duration_ms = int((time.time() - start_time) * 1000)` → `None` / `/1000` / `+` / `* 1001` — value flows **only** into `logger` extra/debug text in these two functions | 40 | **LOW-VALUE** | anomaly_score__mutmut_67, anomaly_score__mutmut_69, similarity__mutmut_51 |
| 4 | `extra={…}` on error logs → `extra=None` / dropped / key renamed `XXduration_msXX`, `DURATION_MS`, `XXstatus_codeXX`, `STATUS_CODE` — structured-log fields nobody asserts | 48 | **LOW-VALUE** | anomaly_score__mutmut_82, anomaly_score__mutmut_87, similarity__mutmut_111 |
| 5 | `exc_info=True` → `None` / `False` / arg dropped on error logs — traceback capture only | 30 | **LOW-VALUE** | anomaly_score__mutmut_83, anomaly_score__mutmut_89, similarity__mutmut_112 |
| 6 | `similarity`: raise message replaced by `None` in all 5 error paths (`CLIPUnavailableError(None, …)`) — same mutants in `anomaly_score` were KILLED because its tests assert message text; similarity's tests assert only type+label | 5 | **TEST-GAP** — `test_clip_client.py::TestSimilarity` (:1106–:1221) never asserts `str(exc)` on error paths | similarity__mutmut_74, similarity__mutmut_95, similarity__mutmut_121 |
| 7 | `original_error=e` → `original_error=None` or arg dropped on every raise (both functions) — exception carries no wrapped cause; `from e` often still set so `__cause__` doesn't save it either (dropped-arg variant). `test_exceptions.py:415` covers only the constructor, not these call sites | 20 | **TEST-GAP** — no test on `anomaly_score`/`similarity` ever inspects `exc_info.value.original_error` | anomaly_score__mutmut_91, anomaly_score__mutmut_93, similarity__mutmut_122 |
| 8 | Breaker endpoint label mutated: `_check_circuit_breaker("similarity")` → `None`/`"XXsimilarityXX"`/`"SIMILARITY"` (and same in `_get_breaker`) — lookup falls back to the **embed** breaker, destroying per-endpoint isolation; existing :1890 test can't tell (see table above) | 12 | **TEST-GAP** | anomaly_score__mutmut_1, anomaly_score__mutmut_5, similarity__mutmut_7 |
| 9 | POST body mutated: payload dict → `None`, `json=payload` → `None`/dropped, keys `image`/`baseline_embedding`/`text` → `XX…XX`/UPPER, `image_b64 = …` → `None`. URL-only tests (:1584/:1634) never open `call_args[1]["json"]` | 16 | **TEST-GAP** | anomaly_score__mutmut_15, anomaly_score__mutmut_18, similarity__mutmut_16 |
| 10 | `headers=self._get_headers()` → `None`/dropped — correlation/traceparent propagation silently lost | 4 | **TEST-GAP** | anomaly_score__mutmut_26, anomaly_score__mutmut_29, similarity__mutmut_24 |
| 11 | `if status_code >= 500:` → `> 500` / `>= 501` — only distinguishable at exactly **500**; tests use 502/503/404/422 | 4 | **TEST-GAP** (boundary) | anomaly_score__mutmut_121, anomaly_score__mutmut_122, similarity__mutmut_105 |
| 12 | `observe_ai_request_duration` args never asserted: label → `None`/`XX…XX`/UPPER (wrong Prometheus series) and `ai_duration = time.time() + ai_start_time` (≈3.5e9 s poisons the histogram). Tests only do `assert_called_once()` | 8 | **TEST-GAP** | anomaly_score__mutmut_31, anomaly_score__mutmut_32, similarity__mutmut_30 |

Totals: EQUIVALENT 33 · LOW-VALUE 118 · TEST-GAP 69 (= rows 6–12). Rows 3–5 are LOW-VALUE, not EQUIVALENT, because they are *real* changes (arithmetic, structured fields, traceback capture) whose only observable effect is diagnostic log content nobody should assert in unit tests.

## Drafted tests (UNVERIFIED — TDD procedure)

Procedure for each (one line): apply the cluster's mutant to a scratch copy of the module, run the new test → must FAIL naming the mutated value; run the same test against original `backend/services/clip_client.py` → must PASS. Not executed here — the live mutation run owns this machine's pytest lane.

Target file for all six: `backend/tests/unit/services/test_clip_client.py` (append; reuses existing `client`, `sample_image`, `valid_embedding` fixtures).

```python
# UNVERIFIED - not yet run red/green
# ---------------------------------------------------------------------------
# Killers for cluster 8 (per-endpoint breaker label, 12 mutants)
# ---------------------------------------------------------------------------
from backend.services.circuit_breaker import CircuitState  # (add to imports)


class TestPerEndpointBreakerIsolation:
    """Each endpoint's circuit breaker must gate only its own endpoint.

    Red on: _check_circuit_breaker("<wrong>") / _get_breaker("<wrong>") mutants
    (they fall back to the embed breaker via dict.get default).
    """

    @pytest.fixture
    def cb_settings(self) -> MagicMock:
        settings = MagicMock()
        settings.clip_url = "http://test-clip:8093"
        settings.ai_connect_timeout = 10.0
        settings.ai_health_timeout = 5.0
        settings.clip_cb_failure_threshold = 3
        settings.clip_cb_recovery_timeout = 30.0
        settings.clip_cb_half_open_max_calls = 2
        return settings

    @pytest.fixture
    def client_cb(self, cb_settings: MagicMock) -> CLIPClient:
        with patch(
            "backend.services.clip_client.get_settings",
            autospec=True,
            return_value=cb_settings,
        ):
            return CLIPClient()

    @pytest.mark.asyncio
    async def test_embed_breaker_open_does_not_block_similarity(
        self, client_cb: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Open the embed breaker; similarity must still reach the service."""
        ok_response = MagicMock()
        ok_response.raise_for_status = MagicMock()
        ok_response.json = MagicMock(return_value={"similarity": 0.5})

        original_http = client_cb._http_client
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=httpx.ConnectError("down"))
        client_cb._http_client = mock_http
        try:
            with (
                patch("backend.services.clip_client.record_pipeline_error", autospec=True),
                patch("backend.services.clip_client.observe_ai_request_duration", autospec=True),
            ):
                for _ in range(3):  # trip embed breaker (threshold 3)
                    with pytest.raises(CLIPUnavailableError):
                        await client_cb.embed(sample_image)
                assert client_cb.get_circuit_breaker_state("embed") is CircuitState.OPEN

                # similarity has its own (still CLOSED) breaker -> must proceed
                mock_http.post = AsyncMock(return_value=ok_response)
                result = await client_cb.similarity(sample_image, "a photo of a cat")
                assert result == 0.5
        finally:
            client_cb._http_client = original_http

    @pytest.mark.asyncio
    async def test_similarity_failures_do_not_open_embed_breaker(
        self, client_cb: CLIPClient, sample_image: Image.Image
    ) -> None:
        """Failures on similarity must be recorded on ITS breaker, not embed's."""
        embedding = [0.1] * EMBEDDING_DIMENSION
        ok_embed = MagicMock()
        ok_embed.raise_for_status = MagicMock()
        ok_embed.json = MagicMock(return_value={"embedding": embedding})

        call_count = 0

        async def failing_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise httpx.ConnectError("down")

        original_http = client_cb._http_client
        mock_http = AsyncMock()
        mock_http.post = failing_post
        client_cb._http_client = mock_http
        try:
            with (
                patch("backend.services.clip_client.record_pipeline_error", autospec=True),
                patch("backend.services.clip_client.observe_ai_request_duration", autospec=True),
            ):
                for _ in range(3):  # trip similarity's own breaker
                    with pytest.raises(CLIPUnavailableError):
                        await client_cb.similarity(sample_image, "a cat")
                assert call_count == 3

                # 4th call: similarity rejected by ITS breaker, without HTTP.
                # _check mutants consult embed's (CLOSED) breaker -> POST runs -> count 4.
                with pytest.raises(CLIPUnavailableError):
                    await client_cb.similarity(sample_image, "a cat")
                assert call_count == 3

                # embed's breaker must be untouched: _get_breaker mutants recorded
                # similarity's failures onto embed -> this would raise.
                assert client_cb.get_circuit_breaker_state("embed") is CircuitState.CLOSED
                mock_http.post = AsyncMock(return_value=ok_embed)
                result = await client_cb.embed(sample_image)
                assert result == embedding
        finally:
            client_cb._http_client = original_http
```

```python
# UNVERIFIED - not yet run red/green
# ---------------------------------------------------------------------------
# Killers for cluster 7 (original_error dropped, 20 mutants)
# ---------------------------------------------------------------------------
class TestErrorChainContract:
    """CLIPUnavailableError from anomaly_score/similarity must carry the cause."""

    @staticmethod
    def _make_error(kind: str) -> Exception:
        if kind == "connect":
            return httpx.ConnectError("connection refused")
        if kind == "timeout":
            return httpx.TimeoutException("slow")
        if kind == "server":
            resp = MagicMock()
            resp.status_code = 503
            return httpx.HTTPStatusError("boom", request=MagicMock(), response=resp)
        if kind == "client":
            resp = MagicMock()
            resp.status_code = 422
            return httpx.HTTPStatusError("bad", request=MagicMock(), response=resp)
        return RuntimeError("kaboom")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("kind", ["connect", "timeout", "server", "client", "unexpected"])
    async def test_anomaly_score_preserves_original_error(
        self, client: CLIPClient, sample_image: Image.Image, valid_embedding: list[float], kind: str
    ) -> None:
        err = self._make_error(kind)
        original_http = client._http_client
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=err)
        client._http_client = mock_http
        try:
            with patch("backend.services.clip_client.record_pipeline_error", autospec=True):
                with pytest.raises(CLIPUnavailableError) as exc_info:
                    await client.anomaly_score(sample_image, valid_embedding)
            assert exc_info.value.original_error is err
            assert exc_info.value.__cause__ is err
        finally:
            client._http_client = original_http

    @pytest.mark.asyncio
    @pytest.mark.parametrize("kind", ["connect", "timeout", "server", "client", "unexpected"])
    async def test_similarity_preserves_original_error(
        self, client: CLIPClient, sample_image: Image.Image, kind: str
    ) -> None:
        err = self._make_error(kind)
        original_http = client._http_client
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=err)
        client._http_client = mock_http
        try:
            with patch("backend.services.clip_client.record_pipeline_error", autospec=True):
                with pytest.raises(CLIPUnavailableError) as exc_info:
                    await client.similarity(sample_image, "a cat")
            assert exc_info.value.original_error is err
            assert exc_info.value.__cause__ is err
        finally:
            client._http_client = original_http
```

```python
# UNVERIFIED - not yet run red/green
# ---------------------------------------------------------------------------
# Killers for clusters 9 (payload, 16) + 10 (headers, 4)
# ---------------------------------------------------------------------------
class TestRequestContract:
    """Success-path POST body/headers are wire contract — assert them."""

    @pytest.mark.asyncio
    async def test_anomaly_score_sends_exact_payload_and_headers(
        self, client: CLIPClient, sample_image: Image.Image, valid_embedding: list[float]
    ) -> None:
        ok_response = MagicMock()
        ok_response.raise_for_status = MagicMock()
        ok_response.json = MagicMock(
            return_value={"anomaly_score": 0.2, "similarity_to_baseline": 0.8}
        )
        original_http = client._http_client
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=ok_response)
        client._http_client = mock_http
        expected_b64 = client._encode_image_to_base64(sample_image)
        sentinel = {"traceparent": "00-abcd-ef01-01", "X-Correlation-ID": "corr-1"}
        try:
            with (
                patch("backend.services.clip_client.observe_ai_request_duration", autospec=True),
                patch(
                    "backend.services.clip_client.get_correlation_headers",
                    autospec=True,
                    return_value=sentinel,
                ),
            ):
                await client.anomaly_score(sample_image, valid_embedding)
            call_kwargs = mock_http.post.call_args[1]
            assert call_kwargs["headers"] == sentinel  # kills headers None/dropped
            payload = call_kwargs["json"]
            assert set(payload) == {"image", "baseline_embedding"}  # kills XX/UPPER/None payload
            assert payload["image"] == expected_b64  # kills image_b64 = None
            assert payload["baseline_embedding"] == valid_embedding
        finally:
            client._http_client = original_http

    @pytest.mark.asyncio
    async def test_similarity_sends_exact_payload_and_headers(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        ok_response = MagicMock()
        ok_response.raise_for_status = MagicMock()
        ok_response.json = MagicMock(return_value={"similarity": 0.42})
        original_http = client._http_client
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=ok_response)
        client._http_client = mock_http
        expected_b64 = client._encode_image_to_base64(sample_image)
        sentinel = {"traceparent": "00-abcd-ef01-01", "X-Correlation-ID": "corr-2"}
        try:
            with (
                patch("backend.services.clip_client.observe_ai_request_duration", autospec=True),
                patch(
                    "backend.services.clip_client.get_correlation_headers",
                    autospec=True,
                    return_value=sentinel,
                ),
            ):
                result = await client.similarity(sample_image, "a person at the door")
            assert result == 0.42
            call_kwargs = mock_http.post.call_args[1]
            assert call_kwargs["headers"] == sentinel
            payload = call_kwargs["json"]
            assert set(payload) == {"image", "text"}
            assert payload["image"] == expected_b64
            assert payload["text"] == "a person at the door"
        finally:
            client._http_client = original_http
```

```python
# UNVERIFIED - not yet run red/green
# ---------------------------------------------------------------------------
# Killer for cluster 11 (status >= 500 boundary, 4 mutants)
# ---------------------------------------------------------------------------
class TestServerErrorBoundary:
    """Exactly 500 must classify as server error (label + message), not client error."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("method", "label"),
        [
            ("anomaly_score", "clip_anomaly_server_error"),
            ("similarity", "clip_server_error"),
        ],
    )
    async def test_exactly_500_is_server_error(
        self, client: CLIPClient, sample_image: Image.Image, valid_embedding: list[float],
        method: str, label: str,
    ) -> None:
        resp = MagicMock()
        resp.status_code = 500
        error = httpx.HTTPStatusError("oops", request=MagicMock(), response=resp)
        original_http = client._http_client
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=error)
        client._http_client = mock_http
        try:
            with patch("backend.services.clip_client.record_pipeline_error", autospec=True) as mock_record:
                with pytest.raises(CLIPUnavailableError) as exc_info:
                    if method == "anomaly_score":
                        await client.anomaly_score(sample_image, valid_embedding)
                    else:
                        await client.similarity(sample_image, "a cat")
            assert "server error: 500" in str(exc_info.value)  # >500/>=501 mutants -> "client error"
            mock_record.assert_called_once_with(label)
        finally:
            client._http_client = original_http
```

```python
# UNVERIFIED - not yet run red/green
# ---------------------------------------------------------------------------
# Killer for cluster 6 (similarity raise message -> None, 5 mutants)
# ---------------------------------------------------------------------------
class TestSimilarityErrorMessages:
    """similarity() error messages are caller-visible contract (mirrors TestAnomalyScore)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("kind", "status", "expected"),
        [
            ("connect", None, "Failed to connect"),
            ("timeout", None, "timed out"),
            ("status", 502, "server error: 502"),
            ("status", 404, "client error: 404"),
            ("unexpected", None, "Unexpected error"),
        ],
    )
    async def test_similarity_error_message_preserved(
        self, client: CLIPClient, sample_image: Image.Image, kind: str, status, expected: str
    ) -> None:
        if kind == "connect":
            err: Exception = httpx.ConnectError("refused")
        elif kind == "timeout":
            err = httpx.TimeoutException("slow")
        elif kind == "unexpected":
            err = RuntimeError("kaboom")
        else:
            resp = MagicMock()
            resp.status_code = status
            err = httpx.HTTPStatusError("err", request=MagicMock(), response=resp)
        original_http = client._http_client
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=err)
        client._http_client = mock_http
        try:
            with patch("backend.services.clip_client.record_pipeline_error", autospec=True):
                with pytest.raises(CLIPUnavailableError) as exc_info:
                    await client.similarity(sample_image, "a cat")
            # message=None mutants give str(exc) == "None"
            assert expected in str(exc_info.value)
        finally:
            client._http_client = original_http
```

```python
# UNVERIFIED - not yet run red/green
# ---------------------------------------------------------------------------
# Killer for cluster 12 (observe_ai_request_duration label + duration, 8 mutants)
# ---------------------------------------------------------------------------
class TestObserveAiDurationArgs:
    """Metric label must match the service registry; duration must be plausible."""

    @pytest.mark.asyncio
    async def test_anomaly_score_observes_clip_anomaly_label(
        self, client: CLIPClient, sample_image: Image.Image, valid_embedding: list[float]
    ) -> None:
        ok_response = MagicMock()
        ok_response.raise_for_status = MagicMock()
        ok_response.json = MagicMock(
            return_value={"anomaly_score": 0.1, "similarity_to_baseline": 0.9}
        )
        original_http = client._http_client
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=ok_response)
        client._http_client = mock_http
        try:
            with patch(
                "backend.services.clip_client.observe_ai_request_duration", autospec=True
            ) as mock_observe:
                await client.anomaly_score(sample_image, valid_embedding)
            (label, duration), _ = mock_observe.call_args
            assert label == "clip_anomaly"  # kills None/XX/CLIP_ANOMALY label mutants
            assert 0.0 <= duration < 60.0  # kills time.time() + start_time (≈3.5e9)
        finally:
            client._http_client = original_http

    @pytest.mark.asyncio
    async def test_similarity_observes_clip_label(
        self, client: CLIPClient, sample_image: Image.Image
    ) -> None:
        ok_response = MagicMock()
        ok_response.raise_for_status = MagicMock()
        ok_response.json = MagicMock(return_value={"similarity": 0.7})
        original_http = client._http_client
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=ok_response)
        client._http_client = mock_http
        try:
            with patch(
                "backend.services.clip_client.observe_ai_request_duration", autospec=True
            ) as mock_observe:
                await client.similarity(sample_image, "a cat")
            (label, duration), _ = mock_observe.call_args
            assert label == "clip"
            assert 0.0 <= duration < 60.0
        finally:
            client._http_client = original_http
```

## WP4.4 disposition notes

- Rows 1–5 (151 mutants, EQUIVALENT/LOW-VALUE): recommend marking as baseline-equivalent; no test work. If a score ceiling is wanted, a `caplog`-based contract test could kill rows 4–5, but asserting internal log record fields couples tests to diagnostics — not recommended.
- Rows 6–12 (69 TEST-GAP mutants): the six drafted classes above cover all of them; each is cheap (mock-post pattern already canonical in this file).
- `test_circuit_breaker_affects_all_methods` (:1890) is itself suspect — it passes whether or not per-endpoint isolation works. Fixing it = adopting the two isolation tests drafted here (or asserting `mock_http.post.call_count` stays flat for the rejected methods).
- If the concurrent run later marks the 699 `null` (untested) keys, expect heavy overlap with rows 3–5 patterns in `embed`/`classify`/`batch_similarity`; this module's error-handling idiom repeats verbatim across five methods.

Raw per-mutant bucket data: `/tmp/wp25/wp44-triage/clusters.json` (key → cluster), `/tmp/wp25/wp44-triage/diffs.txt` (all 220 diffs).
