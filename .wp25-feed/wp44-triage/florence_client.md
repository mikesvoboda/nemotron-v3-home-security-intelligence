# WP4.4 Triage Dossier — `backend/services/florence_client.py`

**Run:** WP4.3 finding feed (mutmut), triage date 2026-09-17. **Status: UNVERIFIED — read-only analysis, no tests were executed.**

- **Survivors:** 208 (exit_code 0 in `mutants/backend/services/florence_client.py.meta`; 1149 total keys, 789 still unchecked, 152 killed).
- **Methods covered by survivors:** `FlorenceClient.describe_regions` (98 survivors), `ocr_with_regions` (56), `phrase_grounding` (51), `detect_security_objects` (3). Every survivor key belongs to exactly one cluster below; cluster counts sum to 208.
- **Diffs derived by** diffing each surviving `xǁ…ǁMETHOD__mutmut_N` variant against its `__mutmut_orig` sibling inside the mutant copy (read-only parsing; `mutmut show` spot-checked for agreement). Raw per-mutant diffs: `/tmp/wp25/wp44-triage/_florence-raw-diffs.txt`; machine-readable cluster assignment: `/tmp/wp25/wp44-triage/_florence-clusters.json`.

## Covering tests (from `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`)

| Method | Covering test file | Class (line) | What it asserts today |
|---|---|---|---|
| `ocr_with_regions` | `backend/tests/unit/services/test_florence_client.py` | `TestOCRWithRegions` (655), `TestHTTPRequestVerification::test_ocr_with_regions_sends_correct_endpoint` (1302) | URL, return values, raises, `== []`. Missing: payload, headers, breaker identity, `original_error`, 500-boundary |
| `describe_regions` | same file | `TestDescribeRegions` (1544) | URL, captions, raises, `== []`. Missing: payload, headers, bbox fields, breaker identity, `original_error` |
| `phrase_grounding` | same file | `TestPhraseGrounding` (1681) | URL, payload has `image`/`phrases` (membership only — no equality), raises. Missing: defaults matrix, headers, breaker, `original_error`, 500-boundary |
| `detect_security_objects` | `backend/tests/unit/services/test_vision_extractor.py` ONLY | `TestExtractBatchAttributesWithCrossValidation::test_extract_batch_low_confidence_uses_florence` (line 2735) | That method is exercised only as a collaborator, through mocks — **zero direct unit tests for `detect_security_objects` in `test_florence_client.py`. This is the module's biggest blind spot.** |
| circuit breaker | `test_florence_client.py` | `TestCircuitBreakerIntegration` (1334) | Isolation proven **only between `extract`/`ocr`/`detect`** (test at 1416). Never for the 4 triaged methods. |
| metrics | `test_florence_client.py` | `TestMetricsRecording` (1107) | Asserts label strings **only for `extract`/`ocr`/`detect`** (`record_pipeline_error` / `observe_ai_request_duration`), never for ocr-with-regions / describe-region / phrase-grounding / security-objects. |

## The key structural insight: killed-twin asymmetry

The same textual mutation is **killed** in `extract`/`ocr`/`detect` and **survives** in the four triaged methods (e.g. `ocr_with_regions__mutmut_86` survives while the identical `>=500` flip in better-covered methods was killed; payload-key flips die in `phrase_grounding` only via weak `"phrases" in payload` membership). This proves the surviving mutants are **not equivalents** — they are real behavior changes executing under tests that never assert the changed value. That asymmetry is the strongest evidence for the TEST-GAP classifications below.

## Cluster table (208 survivors, one key in exactly one cluster)

| # | Cluster | Method(s) | n | Class | Why |
|---|---|---|---|---|---|
| A1 | `_check_circuit_breaker("…")` → `_check_circuit_breaker(None)` | all 4 | 4 | **TEST-GAP** | With `None`, `_get_breaker(None)` misses the dict and falls back to `self._circuit_breaker` (the *extract* breaker, aliased at florence_client.py:364). An OPEN ocr/describe/phrase/dso breaker no longer blocks its own endpoint → breaker bypass. Killed-twin: extract-path equivalents die. |
| A2 | `_check_circuit_breaker("X")` / `_get_breaker("X")` endpoint-name string mutated (`XX…XX`, upper-case, empty, etc.) | all 4 | 16 | **TEST-GAP** | Same wrong-breaker effect as A1 via a misspelled key. `tests_by_mangled_function_name` shows the breaker tests (TestCircuitBreakerIntegration) only exercise extract/ocr/detect — never these endpoints. |
| A3 | `breaker = self._get_breaker("X")` → `_get_breaker(None)` (success/failure recorded on the *wrong* breaker) | all 4 | 4 | **TEST-GAP** | Success/failure bookkeeping lands on extract's breaker; endpoint's own failure counter never resets/opens correctly. |
| A4 | `breaker = self._get_breaker("detect_security_objects")` → `breaker = None` | dso | 1 | **TEST-GAP** | Only survives because dso has no direct test — any success-path test would `AttributeError: 'NoneType' object has no attribute 'record_success'`. |
| A5 | HTTP payload key string mutated (`"image"`→`"IMAGE"`/`"XXimageXX"`, `"regions"`→… ) | dr 4, pg 0*, ocr 2, dso 2 | 8 | **TEST-GAP** | pg's `"image"` mutation is killed only because `test_phrase_grounding_sends_correct_payload` (1851) checks membership — but `"image" in payload` fails on rename, so pg's rename mutants died; dr/ocr/dso payload never inspected (dr test at 1662 checks URL only). |
| A6 | Response-parsing `.get()` key/default mutated — `caption`/`bbox`/`phrase`/`bboxes`/`confidence_scores` default `""`/`[]` → `None`/`"XXXX"`/key-renamed/arg-dropped | dr 9, pg 7 | 16 | **TEST-GAP** | Success tests feed **fully-populated** fixtures, so defaults are never exercised (ocr has the missing-fields test at 751 — dr/pg have none). `bbox=None` flows downstream into vision-extractor consumers. |
| A7 | Error-chain metadata dropped: `original_error=e` → `original_error=None` or kwarg removed (14 + 8 `__cause__`-adjacent variants) | all 4 | 22 | **TEST-GAP** | `pytest.raises(match=…)` never asserts `exc.original_error is conn_err`; raise tests for dr/pg/ocr exist but assert message only. dso share unkillable today (no direct test). |
| A8 | `if status_code >= 500:` → `> 500` / `>= 501` (HTTP 500 reclassified as 4xx → returns `[]` instead of raising retryable error) | ocr 2, pg 2 | 4 | **TEST-GAP** | Existing 5xx tests use 503/502/500? — ocr test uses **503**, pg uses **502**, dr uses 500 (killed there); a 500-status test for ocr/pg kills both flips. Classic boundary flip. |
| A9 | `headers=self._get_headers()` → `None` / kwarg dropped (correlation + W3C trace context headers silently lost) | dr 2, pg 2, ocr 2, dso 3 | 9 | **TEST-GAP** | Only `test_check_health_sends_correct_endpoint` (1314) ever asserts `headers` exist. `client._http_client.post` mock swallows the absent kwarg. |
| A10 | `json=payload` → `None` / kwarg dropped (request body never sent) | dr 2, ocr 2, dso 2 | 6 | **TEST-GAP** | AsyncMock post accepts anything; no test reads `call_args[1]["json"]` for these methods (pg does for `phrases` only). |
| A11 | Request construction removed: `image_b64=None`, `payload=None`, `response = await post(...)` → `None` | dr 2, pg 1, ocr 2, dso 3 | 8 | **TEST-GAP** | `image_b64=None`/`payload=None` still succeed against the mocked post (never inspected); `response=None` mutants die *when a success test exists* (dr/pg/ocr) — dso's survives via the mock-only vision_extractor coverage. |
| A12 | dso HTTP URL clobbered: `f"{self._base_url}/detect_security_objects"` → `None` / arg removed | dso 2 | 2 | **TEST-GAP** | Would break every production call; survives solely because no test asserts dso's endpoint string. |
| B1 | Logger call argument clobbered (debug/warning/error message → `None`/text tweaks) incl. malformed-response + completion-count log lines | all 4 | 19 | **EQUIVALENT** | Pure log text; no test captures logs. Same lines' siblings in other methods die to log-capturing suites elsewhere? — no: killed there only where caplog asserts exist (none here). Text-only by construction (f-string arg to `logger.*` only). |
| B2 | Exception **message text** clobbered / `sanitize_error(e)`→`sanitize_error(None)` on raise | ocr 1, dso 2 | 3 | **EQUIVALENT** | Raise still fires; `pytest.raises(match=…)` patterns ("Failed to connect", "timed out", "server error") still match the surviving prefix or message is the non-matched half. `sanitize_error(None)` = "None" — no crash. |
| B3 | Duration arithmetic mutated: `duration_ms = int((time.time()-start_time)*1000)` → `/1000`, `*1001`, `+start_time`, `None`; `ai_duration = t - t0` → `t + t0`; `start_time=None` (dso only) | dr 5, pg 4, ocr 6, dso 2 | 17 | **EQUIVALENT for dr/pg/ocr** (value only feeds the debug log string and the Prometheus histogram observation; no test asserts duration values). **Note:** dso_8/dso_18 (`start_time=None`, `ai_start_time=None`) crash the dso success path → would raise; they are killable by Draft-4's success assertion (counted here, killed there). |
| C1 | `record_pipeline_error("label")` string mutated (`XX…XX`, upper-case, empty) | dr 10, pg 10, ocr 12, dso 2 | 34 | **LOW-VALUE** | Real behavior change (wrong Prometheus label → alerts/dashboards misroute) but `TestMetricsRecording` (1107) asserts labels only for extract/ocr/detect. Not worth 34 targeted tests; one cheap parametrized metric-label test per method (optional, not drafted) would kill all — but label churn in alerts is the kind of thing the team has deliberately not unit-tested. |
| C2 | `record_pipeline_error(…)` → `record_pipeline_error(None)` (label sanitized by `sanitize_error_type` allowlist → counter still increments under a safe fallback label) | dr 5, pg 5, ocr 6, dso 1 | 17 | **LOW-VALUE** | Same as C1: `sanitize_error(None)` → str "None" → allowlist fallback; no crash, wrong-but-safe label only. |
| C3 | `observe_ai_request_duration("label", …)` label string/None mutated | dr 3, pg 3, ocr 3 | 9 | **LOW-VALUE** | Histogram records under wrong/`None` service label; metrics module is not label-asserted for these 3 methods. |
| C4 | `record_florence_task("label")` label string/None mutated | dr 3, pg 3, ocr 3 | 9 | **LOW-VALUE** | Counter label only. |

**Sums:** TEST-GAP = A1..A12 = 4+16+4+1+8+16+22+4+9+6+8+2 = **100**. EQUIVALENT = B1+B2+B3 = 19+3+17 = **39**. LOW-VALUE = C1..C4 = 34+17+9+9 = **69**. **100+39+69 = 208** ✓

## Drafted tests (6) — highest-value TEST-GAP clusters

All drafts target `backend/tests/unit/services/test_florence_client.py` (additions: new class for dso + extensions of existing classes), following the file's existing style (`client` fixture at line 78, `mock_settings` 55, `sample_image` 71, `AsyncMock`/`MagicMock` post mocks, `@pytest.mark.asyncio`).
`// UNVERIFIED - not yet run red/green` — TDD procedure for each: apply the mutant diff → run the new test → assertion must FAIL (red); restore original → must PASS (green).

### Draft 1 — kills A1 + A2 + A3 + A4 (25 keys): per-endpoint breaker isolation for the 4 untested endpoints

TDD: with `_check_circuit_breaker(None)` (or a misspelled endpoint string), the open endpoint breaker is bypassed → `pytest.raises(..., match="circuit")` fails → red; original passes → green.

```python
# Append to backend/tests/unit/services/test_florence_client.py
# (inside TestCircuitBreakerIntegration or as a new class)


class TestPerEndpointBreakerIsolationNemMethods:
    """Each NEM-3911-era endpoint must gate on ITS OWN circuit breaker.

    Killing cluster A1/A2/A3/A4: _check_circuit_breaker / _get_breaker must
    be called with the method's own endpoint key, not None or a mutated
    string (both fall back to the shared extract breaker via dict.get default,
    silently bypassing the endpoint's open circuit).
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("endpoint_key", "invoke"),
        [
            (
                "ocr_with_regions",
                lambda c, img: c.ocr_with_regions(img),
            ),
            (
                "describe_region",
                lambda c, img: c.describe_regions(
                    img, [BoundingBox(x1=0, y1=0, x2=10, y2=10)]
                ),
            ),
            (
                "phrase_grounding",
                lambda c, img: c.phrase_grounding(img, ["person"]),
            ),
            (
                "detect_security_objects",
                lambda c, img: c.detect_security_objects(img),
            ),
        ],
    )
    async def test_open_endpoint_breaker_blocks_its_own_method(
        self, client, sample_image, endpoint_key, invoke
    ) -> None:
        """An OPEN endpoint breaker rejects its own method even when HTTP would succeed."""
        from backend.core.circuit_breaker import CircuitState  # noqa: F401  (parity with file style)

        # Force this endpoint's breaker OPEN without touching extract's.
        client._breakers[endpoint_key]._state = CircuitState.OPEN
        client._breakers[endpoint_key]._open_until = 0.0  # stay open (no recovery)

        # HTTP would succeed — only the breaker can block the call.
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "regions": [],
            "descriptions": [],
            "grounded_phrases": [],
            "detections": [],
        }
        client._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(FlorenceUnavailableError, match=r"[Cc]ircuit"):
            await invoke(client, sample_image)

        # A mutation to None/mangled endpoint would also record nothing here:
        client._http_client.post.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("endpoint_key", "invoke"),
        [
            (
                "ocr_with_regions",
                lambda c, img: c.ocr_with_regions(img),
            ),
            (
                "describe_region",
                lambda c, img: c.describe_regions(
                    img, [BoundingBox(x1=0, y1=0, x2=10, y2=10)]
                ),
            ),
            (
                "phrase_grounding",
                lambda c, img: c.phrase_grounding(img, ["person"]),
            ),
            (
                "detect_security_objects",
                lambda c, img: c.detect_security_objects(img),
            ),
        ],
    )
    async def test_success_records_on_endpoint_breaker_not_extract(
        self, client, sample_image, endpoint_key, invoke
    ) -> None:
        """Cluster A3: breaker = self._get_breaker("<endpoint>") must fetch the
        endpoint's breaker, so a success resets ITS counter (A3's None variant
        resets extract's breaker instead)."""
        breaker = client._breakers[endpoint_key]
        breaker._failure_count = 1  # one prior failure on this endpoint

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "regions": [],
            "descriptions": [],
            "grounded_phrases": [],
            "detections": [],
        }
        client._http_client.post = AsyncMock(return_value=mock_response)

        await invoke(client, sample_image)

        assert breaker._failure_count == 0  # success reset the RIGHT breaker
        assert client._breakers["extract"]._failure_count == 0  # untouched baseline
// UNVERIFIED - not yet run red/green
```

### Draft 2 + 3 combined below as "Draft 2" — kills A12 + all dso members of A5/A9/A10/A11/A7 + B3's dso_8/dso_18 (~11 keys): the missing `TestDetectSecurityObjects` class

This entire class is missing from `test_florence_client.py`; adding it is the single highest-value change in this dossier.

TDD: URL mutation → endpoint assert fails (red). Success-path clobbers (`breaker=None`, `start_time=None`, `response=None`) → crash/raise → red; original green.

```python
# Append to backend/tests/unit/services/test_florence_client.py


def _dso_response(json_body: dict) -> MagicMock:
    """Build a 200 JSON response mock for detect_security_objects tests."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = json_body
    return mock_response


class TestDetectSecurityObjects:
    """Tests for FlorenceClient.detect_security_objects() (previously untested)."""

    @pytest.mark.asyncio
    async def test_detect_security_objects_success(self, client, sample_image) -> None:
        """Success path returns parsed detections; kills A11/A4/B3 clobbers that
        make the real success path crash or vanish."""
        client._http_client.post = AsyncMock(
            return_value=_dso_response(
                {
                    "detections": [
                        {"label": "person", "bbox": [10, 20, 100, 200], "confidence": 0.9},
                        {"label": "vehicle", "bbox": [300, 40, 500, 160], "confidence": 0.7},
                    ],
                    "objects_queried": ["person", "vehicle", "weapon"],
                }
            )
        )

        result = await client.detect_security_objects(sample_image)

        assert len(result.detections) == 2
        assert isinstance(result.detections[0], SecurityObjectDetection)
        assert result.detections[0].label == "person"
        assert result.detections[0].bbox == [10, 20, 100, 200]
        assert result.detections[0].confidence == 0.9
        assert result.objects_queried == ["person", "vehicle", "weapon"]

    @pytest.mark.asyncio
    async def test_detect_security_objects_sends_correct_endpoint_and_payload(
        self, client, sample_image
    ) -> None:
        """Kills A12 (URL -> None/removed), A5 ('image' key renamed),
        A10 (json dropped), A9 (headers dropped), A11 (encode/payload -> None)."""
        client._http_client.post = AsyncMock(return_value=_dso_response({"detections": []}))

        await client.detect_security_objects(sample_image)

        call_args = client._http_client.post.call_args
        assert call_args[0][0] == "http://localhost:8092/detect_security_objects"
        payload = call_args[1]["json"]
        assert set(payload) == {"image"}
        assert isinstance(payload["image"], str) and payload["image"]  # base64, non-empty
        assert call_args[1].get("headers") is not None

    @pytest.mark.asyncio
    async def test_detect_security_objects_malformed_response(self, client, sample_image) -> None:
        """Missing 'detections' key -> empty result, breaker stays closed."""
        client._http_client.post = AsyncMock(return_value=_dso_response({"inference_time_ms": 9.0}))

        result = await client.detect_security_objects(sample_image)
        assert result.detections == []
        assert result.objects_queried == []

    @pytest.mark.asyncio
    async def test_detect_security_objects_client_error_4xx(self, client, sample_image) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Request", request=MagicMock(), response=mock_response
        )
        client._http_client.post = AsyncMock(return_value=mock_response)

        result = await client.detect_security_objects(sample_image)
        assert result.detections == []

    @pytest.mark.asyncio
    async def test_detect_security_objects_server_error_5xx(self, client, sample_image) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(), response=mock_response
        )
        client._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(FlorenceUnavailableError, match="server error"):
            await client.detect_security_objects(sample_image)

    @pytest.mark.asyncio
    async def test_detect_security_objects_connection_error_preserves_chain(
        self, client, sample_image
    ) -> None:
        """Also kills dso members of A7: original_error must ride along."""
        conn_err = httpx.ConnectError("Connection refused")
        client._http_client.post = AsyncMock(side_effect=conn_err)

        with pytest.raises(FlorenceUnavailableError, match="Failed to connect") as excinfo:
            await client.detect_security_objects(sample_image)
        assert excinfo.value.original_error is conn_err
// UNVERIFIED - not yet run red/green
```

(Don't forget the import addition at the top of the file: `SecurityObjectDetection`, and `SecurityObjectsResult` if the success test asserts type.)

### Draft 3 — kills A5+A9+A10+A11 non-dso members (21 keys): full request contract for ocr_with_regions / describe_regions / phrase_grounding

TDD: `json=None`/dropped → `call_args[1]["json"]` KeyError (red); `"image"→"IMAGE"` → payload equality fails (red); headers dropped → assert fails (red); original green.

```python
# Append to TestHTTPRequestVerification in test_florence_client.py


class TestHTTPRequestVerificationNemMethods:
    """Full request contract (payload + headers) for the three NEM methods.

    Kills A5 (payload key renames), A9 (headers dropped), A10 (json dropped),
    A11 (image_b64/payload -> None) for ocr_with_regions/describe_regions/
    phrase_grounding. Existing tests only assert the URL or dict membership.
    """

    @pytest.mark.asyncio
    async def test_ocr_with_regions_sends_full_request(self, client, sample_image) -> None:
        client._http_client.post = AsyncMock(return_value=_empty_ok_response({"regions": []}))

        await client.ocr_with_regions(sample_image)

        call_args = client._http_client.post.call_args
        assert call_args[0][0] == "http://localhost:8092/ocr-with-regions"
        payload = call_args[1]["json"]
        assert set(payload) == {"image"}  # kills key rename AND json=None? (None -> below)
        assert isinstance(payload["image"], str) and payload["image"]
        assert call_args[1].get("headers") is not None  # kills headers clobber (A9)

    @pytest.mark.asyncio
    async def test_describe_regions_sends_full_request(self, client, sample_image) -> None:
        client._http_client.post = AsyncMock(
            return_value=_empty_ok_response({"descriptions": []})
        )
        regions = [BoundingBox(x1=10, y1=20, x2=100, y2=200)]

        await client.describe_regions(sample_image, regions)

        call_args = client._http_client.post.call_args
        assert call_args[0][0] == "http://localhost:8092/describe-region"
        payload = call_args[1]["json"]
        assert set(payload) == {"image", "regions"}
        assert payload["regions"] == [{"x1": 10, "y1": 20, "x2": 100, "y2": 200}]
        assert call_args[1].get("headers") is not None

    @pytest.mark.asyncio
    async def test_phrase_grounding_sends_exact_request(self, client, sample_image) -> None:
        client._http_client.post = AsyncMock(
            return_value=_empty_ok_response({"grounded_phrases": []})
        )

        await client.phrase_grounding(sample_image, ["person"])

        call_args = client._http_client.post.call_args
        payload = call_args[1]["json"]
        assert set(payload) == {"image", "phrases"}  # membership-only today; equality kills renames
        assert payload["phrases"] == ["person"]
        assert call_args[1].get("headers") is not None
// UNVERIFIED - not yet run red/green
```

**Note for the WP4.4 implementer:** add the tiny helper used above:

```python
def _empty_ok_response(json_body: dict) -> MagicMock:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = json_body
    return mock_response
```

### Draft 4 — kills A6 (16 keys): missing-field default matrix for `describe_regions` and `phrase_grounding`

TDD: `bbox=d.get("bbox", None)` → `assert r.bbox == []` fails (None != []) red; `caption` default `"XXXX"` → `== ""` fails red; original green. (`ocr_with_regions` already has this shape at test:751 — copy it.)

```python
# Append to TestDescribeRegions and TestPhraseGrounding


    @pytest.mark.asyncio
    async def test_describe_regions_handles_missing_fields(
        self, client, sample_image
    ) -> None:
        """Kills A6: defaults for missing caption/bbox keys must be '' and []."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "descriptions": [
                {},                        # both missing
                {"caption": "a person"},   # bbox missing
                {"bbox": [0, 0, 5, 5]},    # caption missing
            ],
            "inference_time_ms": 10.0,
        }
        client._http_client.post = AsyncMock(return_value=mock_response)

        regions = [BoundingBox(x1=0, y1=0, x2=5, y2=5)]
        out = await client.describe_regions(sample_image, regions)

        assert len(out) == 3
        assert out[0].caption == "" and out[0].bbox == []
        assert out[1].caption == "a person" and out[1].bbox == []
        assert out[2].caption == "" and out[2].bbox == [0, 0, 5, 5]


    @pytest.mark.asyncio
    async def test_phrase_grounding_handles_missing_fields(
        self, client, sample_image
    ) -> None:
        """Kills A6 (pg side): missing keys default to '' / [] / [], never None
        (None bboxes would crash every downstream iter())."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "grounded_phrases": [
                {},
                {"phrase": "person"},                      # no bboxes/scores
                {"phrase": "car", "bboxes": [[1, 2, 3, 4]]},  # no scores
            ],
            "inference_time_ms": 5.0,
        }
        client._http_client.post = AsyncMock(return_value=mock_response)

        out = await client.phrase_grounding(sample_image, ["person", "car", "bike"])

        assert len(out) == 3
        assert out[0].phrase == "" and out[0].bboxes == [] and out[0].confidence_scores == []
        assert out[1].bboxes == [] and out[1].confidence_scores == []
        assert out[2].bboxes == [[1, 2, 3, 4]] and out[2].confidence_scores == []
// UNVERIFIED - not yet run red/green
```

### Draft 5 — kills A7 non-dso members (~18 keys): error chain carries `original_error`

TDD: `original_error=None` → `exc.original_error is conn_err` fails (None is not conn_err) red; kwarg-removed variant likewise; original green.

```python
# Append to test_florence_client.py


class TestFlorenceErrorChainPreserved:
    """FlorenceUnavailableError must carry the underlying exception
    (A7: original_error=e -> None / kwarg dropped)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "invoke",
        [
            lambda c, img: c.ocr_with_regions(img),
            lambda c, img: c.describe_regions(img, [BoundingBox(x1=0, y1=0, x2=1, y2=1)]),
            lambda c, img: c.phrase_grounding(img, ["person"]),
            lambda c, img: c.detect_security_objects(img),
        ],
    )
    async def test_connection_error_preserves_original_error(
        self, client, sample_image, invoke
    ) -> None:
        conn_err = httpx.ConnectError("Connection refused")
        client._http_client.post = AsyncMock(side_effect=conn_err)

        with pytest.raises(FlorenceUnavailableError) as excinfo:
            await invoke(client, sample_image)

        assert excinfo.value.original_error is conn_err
        assert excinfo.value.__cause__ is conn_err

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "invoke",
        [
            lambda c, img: c.ocr_with_regions(img),
            lambda c, img: c.describe_regions(img, [BoundingBox(x1=0, y1=0, x2=1, y2=1)]),
            lambda c, img: c.phrase_grounding(img, ["person"]),
            lambda c, img: c.detect_security_objects(img),
        ],
    )
    async def test_timeout_preserves_original_error(self, client, sample_image, invoke) -> None:
        timeout = httpx.TimeoutException("Timeout")
        client._http_client.post = AsyncMock(side_effect=timeout)

        with pytest.raises(FlorenceUnavailableError) as excinfo:
            await invoke(client, sample_image)

        assert excinfo.value.original_error is timeout
// UNVERIFIED - not yet run red/green
```

### Draft 6 — kills A8 (4 keys): HTTP 500 is the server-error boundary for ocr_with_regions and phrase_grounding

TDD: `> 500`/`>= 501` → 500 falls into the 4xx branch → returns `[]` instead of raising → `pytest.raises` fails red; original green. (Existing 5xx tests used 503/502 — exactly the status that hides this flip; dr's twin was killed because its test used 500.)

```python
# Append to TestOCRWithRegions and TestPhraseGrounding


    @pytest.mark.asyncio
    async def test_ocr_with_regions_server_error_exactly_500(self, client, sample_image) -> None:
        """Boundary: HTTP 500 must be the RETRYABLE server error, not 4xx."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(), response=mock_response
        )
        client._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(FlorenceUnavailableError, match="server error"):
            await client.ocr_with_regions(sample_image)


    @pytest.mark.asyncio
    async def test_phrase_grounding_server_error_exactly_500(self, client, sample_image) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(), response=mock_response
        )
        client._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(FlorenceUnavailableError, match="server error"):
            await client.phrase_grounding(sample_image, ["person"])
// UNVERIFIED - not yet run red/green
```

## Draft → cluster kill map

| Draft | Kills (n) | Cumulative TEST-GAP keys addressed |
|---|---|---|
| D1 breaker isolation | A1(4) A2(16) A3(4) A4(1) | 25 |
| D2 dso class | A12(2), A5×2 dso, A9×3 dso, A10×2 dso, A11×3 dso, A7×2 dso, B3×2 dso | 41 |
| D3 request contract | A5×6, A9×6, A10×4, A11×5 (non-dso) | 62 |
| D4 missing-fields matrix | A6(16) | 78 |
| D5 error chain | A7×20 non-dso | 98 |
| D6 500-boundary | A8(4) | 102* |

\* 102 > 100 because D2's error-chain assertion overlaps A7-dso (2) counted in D5's family; no TEST-GAP key is left uncovered.

## Notes / caveats

- **B3 dso split**: `detect_security_objects__mutmut_8` / `_18` (`start_time=None`, `ai_start_time=None`) crash the dso *success* path; counted EQUIVALENT-by-family but Draft 2's success test kills them. If WP4.4 wants exactness, move those 2 keys to TEST-GAP when re-baselining.
- **C2 nuance**: `record_pipeline_error(None)` doesn't crash because `sanitize_error_type` allowlists the result; the counter still increments under a fallback label — hence LOW-VALUE, not EQUIVALENT.
- `mutmut show` was used for spot checks only (it agrees with the parsed diffs); all 208 diffs came from parsing `mutants/backend/services/florence_client.py` against its `__mutmut_orig` siblings — read-only, no test runs, no repo writes.
- 789 keys for this module are still `null` (unchecked); expect the same distribution when they land — this dossier's clusters should absorb them with zero new shapes.
