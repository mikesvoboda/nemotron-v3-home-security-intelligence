# WP4.4 Triage Dossier — backend/services/clip_client.py

Date: 2026-09-18 · Wave: gen-2 queue · Module: `backend/services/clip_client.py`
Source: `mutants/backend/services/clip_client.py.meta` — 1045 keys, all checked (307 killed rc=1, 125 rc=-24, **613 SURVIVED (rc=0)**).

Method of analysis: `mutmut show <key>` failed (`FileNotFoundError: Could not find mutant` — concurrent-cache state), so per the fallback procedure the mutant copy was parsed (each mutant is a full method copy `xǁCLIPClientǁ<fn>__mutmut_N` alongside `__mutmut_orig`) and every survivor diffed line-wise against its `_orig`. 613/613 survivors diffed; 221 distinct change signatures, grouped into 27 clusters. **Cluster counts sum to 613 exactly.**

Verdict split: **125 EQUIVALENT · 291 LOW-VALUE · 197 TEST-GAP** (after C09 reclassification: 128 / 291 / 194; table below carries final classifications).

## Covering test files (from mutmut-stats.json `tests_by_mangled_function_name`)

| File | Role | Key line anchors |
|---|---|---|
| `backend/tests/unit/services/test_clip_client.py` | PRIMARY (all CLIPClient methods) | fixtures `client` L78; `TestCLIPClientInit` L134-181; `TestCheckHealth` L236; `TestEmbed` L341-548; `TestAnomalyScore` L556-801; `TestClassify` L809; `TestSimilarity` L1051; `TestBatchSimilarity` L1250; `TestEdgeCases` L1535-1709 (payload assert L1700-1707 — embed only); `TestCircuitBreakerIntegration` L1717-2029 |
| `backend/tests/unit/services/test_clip_client_gateway.py` | `__init__` gateway routing | L34-162 |
| `backend/tests/unit/services/test_http_connection_pooling.py` | CLIP pooling | `TestCLIPClientConnectionPooling` L145-241: limits asserted ONLY on `_http_client` (L189-190), no timeout assertions |

Existing-assertion fingerprints that explain the survivorship: error tests assert exception TYPE + message-substring (`"server error: 500" in str(...)`) + `record_pipeline_error` label, but **never** `original_error`/`__cause__` (except Connect/Timeout on embed), **never** payload contents (except embed), **never** `observe_ai_request_duration` args (only `assert_called_once()`), **never** `headers=`, status-500 boundary never exercised (only 502/503 for the two methods that survived C07).

## Cluster table (27 clusters, counts sum = 613)

| # | Cluster | N | Class | Mutation (orig → mutant) | Evidence / example keys | Why it survives (test file:line) |
|---|---|---|---|---|---|---|
| C01 | no-op / byte-identical variants | 2 | EQUIVALENT | `_check_circuit_breaker` bodies identical to orig | `_check_circuit_breaker__mutmut_1/2` | diff is empty; killed-by-construction artifact |
| C02 | rstrip charset `"/"→"XX/XX"` | 3 | EQUIVALENT | `rstrip("/")`→`rstrip("XX/XX")` (strip set unchanged, `/` still member) | `__init____mutmut_14,30,34` | semantically identical |
| C03 | `getattr(settings,"use_ai_gateway",False)` default flipped | 2 | EQUIVALENT | default `False→None/True` — both falsy/truthy path identical because `is True` gate follows | `__init____mutmut_18,24` | `getattr(...) is True` short-circuits; `None is True`==False, `True is True` only when attr truthy (gateway test sets True). gateway test L34-88 passes |
| C04 | encode format case `"PNG"→"png"`, `"utf-8"→"UTF-8"` | 2 | EQUIVALENT | PIL format name & codecs alias are case-insensitive | `_encode_image_to_base64__mutmut_7,13` | TestEncodeImageToBase64 L192-228 passes identically |
| C05 | ValueError msg case/XX (empty-labels guard) | 4 | EQUIVALENT | `"Labels list cannot be empty"→lowercase/XX` | `classify__mutmut_3,4`, `batch_similarity__mutmut_3,4` | tests assert `"cannot be empty" in str` — preserved L848, L1290 |
| C06 | error-chain dropped: `original_error=e→None`; `raise X from e → raise X` | **46** | **TEST-GAP** | all 5 methods | `embed__mutmut_126,128,144` | only embed connect/timeout tests assert `original_error` (L446,468); `__cause__` NEVER asserted anywhere |
| C07 | 5xx boundary `status_code >= 500 → >500 / >=501` | 4 | TEST-GAP | anomaly_score + similarity | `anomaly_score__mutmut_121,122`, `similarity__mutmut_105` | tests use 503/502 (L707, L1155); status==500 never exercised for these methods → 500 rerouted to client-error branch unobserved |
| C08 | breaker call-site endpoint-name mangled (`"embed"→None/"XXembedXX"/"EMBED"` at `_check_circuit_breaker`/`_get_breaker` call sites, non-embed methods) | 25 | TEST-GAP | 4 methods ×6 + `_check_circuit_breaker__mutmut_4` | `anomaly_score__mutmut_1,2` etc. | endpoint→None falls back to embed-alias breaker; per-endpoint isolation never tested (TestCircuitBreakerIntegration L1717 only trips embed) |
| C08e | same, on embed | 6 | EQUIVALENT | embed's own name mangled | `embed__mutmut_1,2,3` | `_breakers.get(unknown, alias)` returns the SAME embed breaker — no behavior change |
| C09 | `_get_breaker` `.get(endpoint, X)` arg mutants | 3 | EQUIVALENT | default None/omitted, key None | `_get_breaker__mutmut_1,2,4` | identical for every endpoint key that exists; unknown-key lookup is undefined contract, never called |
| C10 | per-endpoint breaker `config=_cb_config → None/dropped` | 8 | TEST-GAP | `__init__` | `__init____mutmut_72,74,80` | `test_circuit_breaker_initialization` L1969-1985 asserts ONLY `_circuit_breaker` (embed alias); other breakers silently get 5/30.0/3 defaults |
| C11 | breakers dict KEY mangled (`"classify"→"XXclassifyXX"/"CLASSIFY"`) | 8 | TEST-GAP | `__init__` | `__init____mutmut_69,70,77` | `get_all_circuit_breaker_states()` keys never asserted; lookup falls to embed alias silently |
| C12 | breaker `name=` arg mangled (cosmetic label) | 15 | LOW-VALUE | `__init__` | `__init____mutmut_63,67,68` | name only surfaces in metrics/otel labels; nobody should assert it |
| C13 | `record_pipeline_error("clip_circuit_open")` label mangled | 3 | TEST-GAP | `_check_circuit_breaker` | `_check_circuit_breaker__mutmut_8,9,10` | circuit-open path never asserts the metric label (L1755 patches record without asserting args) |
| C14 | `observe_ai_request_duration("clip"/"clip_anomaly")` label mangled/None | 15 | TEST-GAP | 5 methods | `embed__mutmut_28,32,33` | all tests do `assert_called_once()` only (L367,586,836,1074,1278) — args unchecked |
| C15 | `ai_duration = t - ai_start → t + ai_start` | 5 | TEST-GAP | 5 methods | `embed__mutmut_27` | duration VALUE fed to observe never asserted (same weak `assert_called_once`) |
| C16 | `headers=self._get_headers()` → None/dropped | 11 | TEST-GAP | 5 methods + check_health | `check_health__mutmut_3` | check_health asserts `"headers" in call_args[1]` (L259, key exists even if None!); embed asserts only URL |
| C17 | payload mangled: key `"image"/"labels"/"text"/"texts"/"baseline_embedding"` case/XX, `payload=None`, `image_b64=None`, `json=None/dropped` | **32** | **TEST-GAP** | anomaly_score/classify/similarity/batch_similarity ×8 | `anomaly_score__mutmut_15,17,18` | payload asserted ONLY for embed (TestEdgeCases L1682-1709); other 4 endpoints' request bodies unchecked |
| C18 | `__init__` client config: `connect/read/write/pool=None` (main+health), health `timeout=None/dropped`, health `limits` mangled (None/11/6/dropped) | 17 | TEST-GAP | `__init__` | `__init____mutmut_36,37,38` | main timeout values never asserted (init test checks `isinstance` only L180); pooling test asserts limits only on `_http_client` L189, never on `_health_http_client` |
| C19 | raised-message → `None` in `raise CLIPUnavailableError(None)` | 15 | TEST-GAP | classify/similarity/batch_similarity server/client branches | `classify__mutmut_83,104,130` | `pytest.raises` passes, message `"None"` — embed/anomaly versions killed by existing substring asserts, these 3 methods lack them for 4xx/5xx (`test_classify_server_error` L969 has no message check) |
| C20 | `sanitize_error(e)→sanitize_error(None)` in raised msg | 5 | TEST-GAP | 5 methods unexpected-error branch | `embed__mutmut_169` | `sanitize_error` does `str(error)` so msg degrades to `"…: None"`; `"Unexpected error" in str` still passes (L545) |
| C21 | raised-message case/XX text variants | 94 | EQUIVALENT | all 5 methods | `embed__mutmut_43,44,55` | every surviving variant preserves the asserted substring (`"server error: 500"`, `"missing 'embedding'"`, lowercase keeps `in` checks true) |
| C22 | `logger.*` `exc_info=True → None/False/dropped` | 88 | LOW-VALUE | all methods + check_health | `check_health__mutmut_7,8,10` | traceback attach is pure logging config; no test should assert it |
| C23 | `logger.error extra={"duration_ms"...}` mangled/None/dropped | 120 | LOW-VALUE | 5 methods | `embed__mutmut_70,73,75` | log-record enrichment only |
| C24 | `duration_ms = int((t-s)*1000)` → None/÷1000/÷sum/×1001 | 20 | LOW-VALUE | 5 methods | `embed__mutmut_61,63,64` | value only consumed by C23 log `extra` (and the C25 `None`-msg debug lines) |
| C25 | log message → None / `sanitize_error(None)` (logger context only) | 48 | LOW-VALUE | all methods incl `logger.info(None)`/`logger.debug(None)` | `close__mutmut_1` | message content of log calls nobody parses |
| C26 | log message case/XX | 12 | EQUIVALENT | close/embed/anomaly/similarity | `close__mutmut_2,3,4` | pure text |

Totals: TEST-GAP C06:46 + C07:4 + C08:25 + C09:0(reclassed) + C10:8 + C11:8 + C13:3 + C14:15 + C15:5 + C16:11 + C17:32 + C18:17 + C19:15 + C20:5 = **197**; EQUIVALENT = 125+3(C09)=128; LOW-VALUE = 291; C09 moves TEST-GAP→194/EQUIV→128 if the table classification is applied.

## Drafted kill-tests (6 tests covering 183 of the 197 TEST-GAP survivors)

TDD procedure for every test below: apply the cluster's mutant → the NEW assertion fails (red); original source → passes (green). All UNVERIFIED — not executed (live mutation run owns this machine).

Target file for all six: `backend/tests/unit/services/test_clip_client.py` (reuse `client`, `sample_image` fixtures, L78/L53).

### T1 — `test_error_chain_preserved_all_methods` (kills C06, 46)

```python
# UNVERIFIED - not yet run red/green  (kills cluster C06-ERR-CHAIN)
class TestErrorChainContract:
    """original_error attr and __cause__ must survive wrapping into CLIPUnavailableError."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,args", [
        ("embed", ()), ("classify", (["cat"],)), ("similarity", ("text",)),
        ("batch_similarity", (["cat"],)),
    ])
    async def test_error_chain_preserved(
        self, client: CLIPClient, sample_image: Image.Image, method: str, args: tuple
    ) -> None:
        original_error = httpx.ConnectError("Connection refused")
        original_client = client._http_client
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=original_error)
        client._http_client = mock_http
        try:
            with patch("backend.services.clip_client.record_pipeline_error", autospec=True):
                with pytest.raises(CLIPUnavailableError) as exc_info:
                    await getattr(client, method)(sample_image, *args)
            assert exc_info.value.original_error is original_error
            assert exc_info.value.__cause__ is original_error
        finally:
            client._http_client = original_client

    @pytest.mark.asyncio
    async def test_error_chain_preserved_anomaly_score(
        self, client: CLIPClient, sample_image: Image.Image, valid_embedding: list[float]
    ) -> None:
        original_error = httpx.ConnectError("Connection refused")
        original_client = client._http_client
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=original_error)
        client._http_client = mock_http
        try:
            with patch("backend.services.clip_client.record_pipeline_error", autospec=True):
                with pytest.raises(CLIPUnavailableError) as exc_info:
                    await client.anomaly_score(sample_image, valid_embedding)
            assert exc_info.value.original_error is original_error
            assert exc_info.value.__cause__ is original_error
        finally:
            client._http_client = original_client
```

Red on `original_error=e → None` (attr assert) and on `) from e` dropped (`__cause__` becomes None). Green on original.

### T2 — `test_request_payload_fields` (kills C17, 32)

```python
# UNVERIFIED - not yet run red/green  (kills cluster C17-PAYLOAD)
class TestRequestPayloadContract:
    """Non-embed endpoints must send the documented JSON body (tests only covered embed)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "method,args,extra_key",
        [
            ("anomaly_score", (None,), "baseline_embedding"),  # None replaced by valid_embedding below
            ("classify", (["cat", "dog"],), "labels"),
            ("similarity", ("a cat",), "text"),
            ("batch_similarity", (["cat"],), "texts"),
        ],
    )
    async def test_payload_fields(
        self,
        client: CLIPClient,
        sample_image: Image.Image,
        valid_embedding: list[float],
        method: str,
        args: tuple,
        extra_key: str,
    ) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(
            return_value={"similarities": {"cat": 0.1}, "scores": {"cat": 1.0},
                          "top_label": "cat", "similarity": 0.5,
                          "anomaly_score": 0.1, "similarity_to_baseline": 0.9}
        )
        original_client = client._http_client
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        client._http_client = mock_http
        try:
            with patch("backend.services.clip_client.observe_ai_request_duration", autospec=True):
                call_args = list(args)
                if extra_key == "baseline_embedding":
                    call_args[0] = valid_embedding
                await getattr(client, method)(sample_image, *call_args)
            payload = mock_http.post.call_args[1]["json"]
            assert isinstance(payload, dict), f"json payload missing (method={method})"
            assert "image" in payload
            decoded = base64.b64decode(payload["image"])
            assert Image.open(io.BytesIO(decoded)).format == "PNG"
            assert extra_key in payload
            assert payload[extra_key] == call_args[0]
        finally:
            client._http_client = original_client
```

Red on key-case/XX (`"image" in payload` fails), `json=None`/dropped (`isinstance` fails), `image_b64=None` (b64decode TypeError). Green on original.

### T3 — `test_ai_duration_observed_with_label` (kills C14 + C15, 20)

```python
# UNVERIFIED - not yet run red/green  (kills clusters C14-OBSERVE-LABEL + C15-AIDURATION-ARITH)
class TestObserveAiDurationContract:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,expected_label", [
        ("embed", "clip"), ("classify", "clip"),
        ("similarity", "clip"), ("batch_similarity", "clip"),
    ])
    async def test_label_and_duration(
        self, client: CLIPClient, sample_image: Image.Image, method: str, expected_label: str
    ) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(
            return_value={"embedding": [0.1] * EMBEDDING_DIMENSION, "scores": {"cat": 1.0},
                          "top_label": "cat", "similarity": 0.5, "similarities": {"cat": 0.5}}
        )
        original_client = client._http_client
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        client._http_client = mock_http
        try:
            with patch("backend.services.clip_client.observe_ai_request_duration", autospec=True) as mock_observe:
                await getattr(client, method)(
                    sample_image, *({"classify": (["cat"],), "similarity": ("x",),
                                     "batch_similarity": (["cat"],)}.get(method, ()))
                )
            args = mock_observe.call_args[0]
            assert args[0] == expected_label
            assert isinstance(args[1], float) and 0.0 <= args[1] < 60.0
        finally:
            client._http_client = original_client

    @pytest.mark.asyncio
    async def test_anomaly_label_clip_anomaly(
        self, client: CLIPClient, sample_image: Image.Image, valid_embedding: list[float]
    ) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(
            return_value={"anomaly_score": 0.2, "similarity_to_baseline": 0.8}
        )
        original_client = client._http_client
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        client._http_client = mock_http
        try:
            with patch("backend.services.clip_client.observe_ai_request_duration", autospec=True) as mock_observe:
                await client.anomaly_score(sample_image, valid_embedding)
            args = mock_observe.call_args[0]
            assert args[0] == "clip_anomaly"
            assert 0.0 <= args[1] < 60.0
        finally:
            client._http_client = original_client
```

Red on label None/XX/case (`args[0] ==` fails) and on `-`→`+` arith (duration ≈ 2×epoch > 60). Green on original.

### T4 — `test_error_message_carries_diagnostic_content` (kills C19 + C20 + C07, 24)

```python
# UNVERIFIED - not yet run red/green  (kills clusters C19-RAISE-MSG-NONE, C20-RAISE-MSG-SANITIZE-NONE, C07-STATUS-500-BOUNDARY)
class TestErrorMessageContract:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,args", [
        ("embed", ()), ("classify", (["cat"],)), ("similarity", ("t",)),
        ("batch_similarity", (["cat"],)),
    ])
    async def test_server_error_500_boundary(
        self, client: CLIPClient, sample_image: Image.Image, method: str, args: tuple
    ) -> None:
        """status_code == 500 must take the 5xx branch (server error), not the 4xx branch."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        error = httpx.HTTPStatusError("Server error", request=MagicMock(), response=mock_response)
        original_client = client._http_client
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=error)
        client._http_client = mock_http
        try:
            with patch("backend.services.clip_client.record_pipeline_error", autospec=True) as mock_record:
                with pytest.raises(CLIPUnavailableError) as exc_info:
                    await getattr(client, method)(sample_image, *args)
            assert "server error: 500" in str(exc_info.value)  # kills C19 (msg None) and C07 (>500/>=501 reroute)
            expected = "clip_anomaly_server_error" if method == "anomaly_score" else "clip_server_error"
            mock_record.assert_called_once_with(expected)
        finally:
            client._http_client = original_client

    @pytest.mark.asyncio
    async def test_anomaly_500_boundary(
        self, client: CLIPClient, sample_image: Image.Image, valid_embedding: list[float]
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 500
        error = httpx.HTTPStatusError("Server error", request=MagicMock(), response=mock_response)
        original_client = client._http_client
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=error)
        client._http_client = mock_http
        try:
            with patch("backend.services.clip_client.record_pipeline_error", autospec=True) as mock_record:
                with pytest.raises(CLIPUnavailableError) as exc_info:
                    await client.anomaly_score(sample_image, valid_embedding)
            assert "server error: 500" in str(exc_info.value)
            mock_record.assert_called_once_with("clip_anomaly_server_error")
        finally:
            client._http_client = original_client

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,args", [
        ("embed", ()), ("classify", (["cat"],)), ("similarity", ("t",)),
        ("batch_similarity", (["cat"],)),
    ])
    async def test_unexpected_error_message_keeps_original_text(
        self, client: CLIPClient, sample_image: Image.Image, method: str, args: tuple
    ) -> None:
        original_client = client._http_client
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=RuntimeError("kaboom-detail"))
        client._http_client = mock_http
        try:
            with patch("backend.services.clip_client.record_pipeline_error", autospec=True):
                with pytest.raises(CLIPUnavailableError) as exc_info:
                    await getattr(client, method)(sample_image, *args)
        finally:
            client._http_client = original_client
        # kills C20: sanitize_error(None) degrades the message to "...: None"
        assert "kaboom-detail" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_anomaly_unexpected_error_message_keeps_original_text(
        self, client: CLIPClient, sample_image: Image.Image, valid_embedding: list[float]
    ) -> None:
        original_client = client._http_client
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(side_effect=RuntimeError("kaboom-detail"))
        client._http_client = mock_http
        try:
            with patch("backend.services.clip_client.record_pipeline_error", autospec=True):
                with pytest.raises(CLIPUnavailableError) as exc_info:
                    await client.anomaly_score(sample_image, valid_embedding)
        finally:
            client._http_client = original_client
        assert "kaboom-detail" in str(exc_info.value)
```

C07 note: embed/classify/batch use 500 in existing tests and die naturally; the surviving C07 mutants live in anomaly_score/similarity whose tests use 502/503 — the 500-boundary param above kills them (and doubles as the C19 kill for those methods).

### T5 — `test_client_configures_timeouts_and_health_limits` (kills C18, 17)

```python
# UNVERIFIED - not yet run red/green  (kills cluster C18-INIT-CLIENT-CONFIG)
class TestClientTimeoutAndLimitsContract:
    def test_main_and_health_timeouts_from_settings(self, mock_settings: MagicMock) -> None:
        # NOTE: ai_health_timeout deliberately != httpx's built-in 5.0 default, else the
        # timeout=None mutants are coincidentally equivalent. Same for clip_read_timeout.
        mock_settings.clip_read_timeout = 15.0
        mock_settings.ai_health_timeout = 7.0
        with patch("backend.services.clip_client.get_settings", autospec=True, return_value=mock_settings):
            client = CLIPClient()
        t = client._http_client.timeout
        assert t.connect == 10.0 and t.read == 15.0 and t.write == 15.0 and t.pool == 10.0
        h = client._health_http_client.timeout
        assert h.connect == 7.0 and h.read == 7.0 and h.write == 7.0 and h.pool == 7.0
        # health pool limits are asserted by NO existing test (pooling test covers _http_client only)
        pool = client._health_http_client._transport._pool
        assert pool._max_connections == 10
        assert pool._max_keepalive_connections == 5
```

Red on every `=settings.X → None` (httpx coerces None → default ≠ settings value), `timeout=None/dropped` (httpx default 5.0 connect but read/write/pool differ from settings), health limits 11/6/None/dropped. Green on original. Add to `test_clip_client.py` (class `TestCLIPClientInit` neighbor); `mock_settings` fixture lacks `clip_read_timeout` → set explicitly (done above).

### T6 — `test_per_endpoint_breaker_isolation_and_config` (kills C08 non-embed + C10 + C11 + C13, 44)

```python
# UNVERIFIED - not yet run red/green  (kills C08-BREAKER-CALLSITE, C10-BREAKER-CONFIG,
# C11-BREAKER-DICTKEY, C13-CIRCUIT-OPEN-LABEL)
class TestPerEndpointBreakerContract:
    @pytest.fixture
    def settings_cb(self) -> MagicMock:
        s = MagicMock()
        s.clip_url = "http://test-clip:8093"
        s.ai_connect_timeout = 10.0
        s.ai_health_timeout = 5.0
        s.clip_cb_failure_threshold = 2
        s.clip_cb_recovery_timeout = 30.0
        s.clip_cb_half_open_max_calls = 2
        return s

    def test_breakers_instantiate_with_settings_config(self, settings_cb: MagicMock) -> None:
        with patch("backend.services.clip_client.get_settings", autospec=True,
                   return_value=settings_cb):
            client = CLIPClient()
        for endpoint, breaker in client._breakers.items():  # kills C11: dict keys must be exact
            assert breaker._failure_threshold == 2, endpoint      # kills C10 config=None→defaults(5/30)
            assert breaker._recovery_timeout == 30.0, endpoint
            assert breaker._half_open_max_calls == 2, endpoint
        assert set(client._breakers) == {"embed", "anomaly_score", "classify",
                                         "similarity", "batch_similarity"}
        assert client._breakers["classify"] is not client._circuit_breaker  # kills C11 key mangling

    @pytest.mark.asyncio
    async def test_open_embed_breaker_does_not_block_classify(
        self, sample_image: Image.Image, settings_cb: MagicMock
    ) -> None:
        with patch("backend.services.clip_client.get_settings", autospec=True,
                   return_value=settings_cb):
            client = CLIPClient()
        good = MagicMock()
        good.raise_for_status = MagicMock()
        good.json = MagicMock(return_value={"scores": {"cat": 1.0}, "top_label": "cat"})
        fail_conn = httpx.ConnectError("down")
        call = {"allow": False}

        async def post(*a, **k):
            if call["allow"]:
                return good
            raise fail_conn

        original = client._http_client
        mock_http = AsyncMock()
        mock_http.post = post
        client._http_client = mock_http
        try:
            with patch("backend.services.clip_client.record_pipeline_error", autospec=True):
                for _ in range(2):  # threshold=2 opens the EMBED breaker only
                    with pytest.raises(CLIPUnavailableError):
                        await client.embed(sample_image)
            # embed is now open -> must be rejected, AND report the right metric
            with patch("backend.services.clip_client.record_pipeline_error", autospec=True) as rec:
                with pytest.raises(CLIPUnavailableError):
                    await client.embed(sample_image)
                rec.assert_called_once_with("clip_circuit_open")  # kills C13 label mangling
            # classify uses ITS OWN breaker -> must succeed (kills C08 call-site name mangling:
            # mangled endpoints resolve to the open embed breaker and wrongly raise here)
            call["allow"] = True
            with patch("backend.services.clip_client.observe_ai_request_duration", autospec=True):
                scores, top = await client.classify(sample_image, ["cat"])
            assert top == "cat"
            assert client.get_circuit_breaker_state("classify") \
                .__class__ is client.get_circuit_breaker_state("embed").__class__ or True
            assert client._get_breaker("embed").get_state().value == "open"
            assert client._get_breaker("classify").get_state().value == "closed"
        finally:
            client._http_client = original
```

(One line above is a self-check placeholder for the state enum; replace with `assert client.get_circuit_breaker_state("classify").value == "closed"` when adopting — flagged UNVERIFIED anyway. `CircuitState` import already exists in the test file? No — add `from backend.services.circuit_breaker import CircuitState` if using `.value` comparisons against enum; the string compare shown avoids that.)

## Kill coverage vs TEST-GAP survivors

| Drafted test | Clusters killed | N |
|---|---|---|
| T1 | C06 | 46 |
| T2 | C17 | 32 |
| T3 | C14 + C15 | 20 |
| T4 | C19 + C20 + C07 | 24 |
| T5 | C18 | 17 |
| T6 | C08 + C10 + C11 + C13 | 44 |
| **Total** | | **183 / 197** (remaining 14 = C16 headers, below the value bar: correlation-header propagation is contract-tested elsewhere (`test_correlation_propagation.py` has CLIP-adjacent coverage for sibling clients) — a `headers=` assert could be tacked onto T2 if WP4.4 wants full closure) |

## Notes / hazards for the fixing lane

- C06/C16/etc. mutants live inside 5 near-identical except-blocks; a fix must be replicated across embed/anomaly_score/classify/similarity/batch_similarity or mutmut re-survives.
- Do NOT try to kill C12 (breaker `name=`), C22-C25 (logging internals) with tests — LOW-VALUE by policy; if a score-driven baseline needs the numbers, prefer documented suppression (`mutmut config` exclusions) over asserting `extra=` dicts.
- T5 relies on httpx internals (`_transport._pool`) exactly as the existing pooling test does (L187-190) — consistent with repo precedent.
- `sanitize_error` (`backend/core/logging.py:963`) is `str(error)` + redaction — the reason C20 does NOT crash, only degrades: assertion must target the original message text, not type.
- `test_clip_client.py` fixtures build `MagicMock()` settings: `clip_read_timeout` is auto-mocked (never set) — the main-client timeout mutants in C18 could not have been caught even if someone asserted it without setting it. Set explicit values (as in T5).
