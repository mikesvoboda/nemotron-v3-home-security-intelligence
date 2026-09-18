# WP4.4 Triage Dossier — backend/services/enrichment_client.py

Generated: 2026-09-17 (WP4.3 finding feed → WP4.4). **STATUS: UNVERIFIED — no tests were run (live mutation run owns the machine); diffs taken from `mutants/backend/services/enrichment_client.py` variant blocks, verified against `mutmut show` spot-check.**

- Verdict source: `mutants/backend/services/enrichment_client.py.meta` → `exit_code_by_key` (`0` = survived). 2567 keys total; **158 survivors**; 434 killed; 1975 not yet checked (nulls — this triage covers only currently-survived keys).
- Diff extraction: each `__mutmut_N` variant block in the mutant copy diffed against its `__mutmut_orig` sibling (script: `/tmp/wp25/diff_survivors.py`; raw diffs: `/tmp/wp25/survivor_diffs.txt`). `uv run mutmut show <key>` confirmed identical output on a sample key.

## Covering test files

| File                                                                    | Key regions                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| ----------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/tests/unit/services/test_enrichment_client.py` (3046 ln)       | per-class fixtures/asserts: VehicleClassificationResult :188 (commercial :222), ClothingClassificationResult :279 (:317/:334), ActionClassificationResult :472 (context :497/:505, has_security_alerts :520–551), PoseAnalysisResult :554 (alert labels :588–649), CircuitBreaker :1910–1973, RetryLogic :1976 (`_is_retryable_error` :1995–2025, retry loop :2027), Unified{Pose,Clothing,Demographics,Vehicle,Threat}Result :2263/:2307/:2347/:2378/:2427, UnifiedEnrichmentResult :2468 (`to_dict` :2508–2518), EnrichDetection :2597, ModelStatus :2854, PreloadModel :2902, ParseUnifiedResponse :2952–3046 |
| `backend/tests/unit/services/test_enrichment_client_circuit_breaker.py` | `TestCircuitBreakerStateAPI.test_is_circuit_open` :428–438, `test_reset_circuit_breaker(_single_endpoint)` :440–465                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| `backend/tests/unit/services/test_enrichment_client_errors.py`          | 500-path integration test :409–426 (asserts only `"failed after … retries"` — survives retry mutants because the non-retryable path raises the same message)                                                                                                                                                                                                                                                                                                                                                                                                                                                     |

Source anchors in `backend/services/enrichment_client.py`: parse `.get` lines 3059–3107; `_is_retryable_error` 1082; breaker `get(endpoint, self._breakers["enrich"])` 1020/1034; `get_model_status` 3256–3270; `preload_model` 3287–3297; context-string builders/labels at 98–107, 189–204, 316–340, 399–436, 500–540, 576–637, 677–699.

## Cluster table (counts sum = 158)

| #   | Cluster                                                                                                                                                                                                                                                                      | Count | Class      | Examples (≤3)                                                                                                                                                    |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----- | ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| C1  | `_parse_unified_response`: **default branch** of `X.get(key, default)` flipped (`0.0`→`None`/`1.0`/omitted, `"unknown"`→`None`/`"UNKNOWN"`/`"XXunknownXX"`, `False`→`None`/`True`, `[]`→omitted, `"none"`→`"NONE"`/`None`) — src 3059–3107                                   | 50    | TEST-GAP   | `_parse_unified_response__mutmut_10`, `__mutmut_105`, `__mutmut_58`                                                                                              |
| C2  | `_parse_unified_response`: **lookup key** of `.get(...)` clobbered (`"age_confidence"`→`None`/`0.0`/`"XXage_confidenceXX"`/`"AGE_CONFIDENCE"`, same for 14 other keys) — src 3059–3107                                                                                       | 35    | TEST-GAP   | `_parse_unified_response__mutmut_106`, `__mutmut_111`, `__mutmut_200`                                                                                            |
| C3  | `_parse_unified_response`: whole field expression → `None` (`keypoints=None`, `confidence=None`, `categories=None`, `age_confidence=None`, `gender_confidence=None`, `color=None`, `threats=None`, `max_severity=None`)                                                      | 9     | TEST-GAP   | `_parse_unified_response__mutmut_137`, `__mutmut_176`, `__mutmut_66`                                                                                             |
| C4  | `to_context_string` ALERT/tag literals XX-padded or CAPS-swapped (Clothing/Pose/UnifiedPose/UnifiedClothing/Vehicle/UnifiedThreat) — tests assert only `"ALERT" in ctx` / `"suspicious" in ctx.lower()` substrings                                                           | 13    | TEST-GAP   | `ClothingClassificationResult.to_context_string__mutmut_3`, `PoseAnalysisResult.to_context_string__mutmut_20`, `UnifiedThreatResult.to_context_string__mutmut_2` |
| C5  | `UnifiedClothing/ThreatResult.to_context_string` fallback defaults inside `top.get('category','unknown')`/`t.get('type','unknown')` clobbered — dead under fixtures that always populate the keys                                                                            | 11    | LOW-VALUE  | `UnifiedClothingResult.to_context_string__mutmut_8`, `UnifiedThreatResult.to_context_string__mutmut_7`, `__mutmut_13`                                            |
| C6  | `UnifiedEnrichmentResult.to_dict`: field-name literals (`"vehicle"`,`"pet"`,`"action"`,`"depth"` → `VEHICLE`/`XXpetXX`/…) clobbered + `result[field_name]=field_value.to_dict()`→`= None` — existing test only asserts membership for pose/clothing/demographics/threat/reid | 9     | TEST-GAP   | `to_dict__mutmut_10`, `__mutmut_14`, `__mutmut_17`                                                                                                               |
| C7  | join separator `"\n"`→`"XX\nXX"` (6 builders), `' '`→`'XX XX'`, `', '`→`'XX, XX'` — substring-only tests can't see the separator                                                                                                                                             | 8     | LOW-VALUE  | `ActionClassificationResult.to_context_string__mutmut_6`, `UnifiedVehicleResult.to_context_string__mutmut_7`, `UnifiedThreatResult.to_context_string__mutmut_15` |
| C8  | `get_model_status`/`preload_model` HTTP call args: URL→`None`/omitted, `headers=self._get_headers()`→`None`/omitted — NEM-3147 trace-context headers unasserted on these 2 endpoints                                                                                         | 6     | TEST-GAP   | `get_model_status__mutmut_2`, `__mutmut_3`, `preload_model__mutmut_4`                                                                                            |
| C9  | `cast("dict[str, Any]", ...)` type-string / `cast(None, ...)` clobbered — `typing.cast` is runtime-inert                                                                                                                                                                     | 4     | EQUIVALENT | `get_model_status__mutmut_6`, `__mutmut_10`, `__mutmut_12`                                                                                                       |
| C10 | `logger.warning/info(f"…")`→`logger.warning/info(None)` in get_model_status/preload_model — zero `caplog` assertions in this module's tests                                                                                                                                  | 4     | LOW-VALUE  | `get_model_status__mutmut_13`, `preload_model__mutmut_12`, `__mutmut_16`                                                                                         |
| C11 | `is_circuit_open`/`reset_circuit_breaker`: `breakers.get(endpoint, breakers["enrich"])` fallback dropped → `AttributeError` (None) for unknown endpoint names                                                                                                                | 4     | TEST-GAP   | `is_circuit_open__mutmut_4`, `reset_circuit_breaker__mutmut_6`                                                                                                   |
| C12 | `_is_retryable_error`: `status_code >= 500` → `> 500` / `>= 501` (HTTP 500 boundary)                                                                                                                                                                                         | 2     | TEST-GAP   | `_is_retryable_error__mutmut_4`, `__mutmut_5`                                                                                                                    |
| C13 | `ActionClassificationResult.has_security_alerts`: `risk_weight >= 0.7` → `> 0.7` (0.7 boundary)                                                                                                                                                                              | 1     | TEST-GAP   | `has_security_alerts__mutmut_2`                                                                                                                                  |
| C14 | `get_model_status` error payload: `{"error": str(e)}` → `{"error": str(None)}` (literal `"None"`)                                                                                                                                                                            | 1     | TEST-GAP   | `get_model_status__mutmut_16`                                                                                                                                    |
| C15 | `UnifiedClothingResult.to_context_string` guard `if self.categories` → `if (self.categories) or True` — unreachable change (preceding `if not self.categories: return` guard)                                                                                                | 1     | EQUIVALENT | `to_context_string__mutmut_4`                                                                                                                                    |

**Sum: 50+35+9+13+11+9+8+6+4+4+4+2+1+1+1 = 158.** TEST-GAP: C1–C4, C6, C8, C11–C14 (129). LOW-VALUE: C5, C7, C10 (23). EQUIVALENT: C9, C15 (5).

## Full cluster memberships

- **C1 (50)**: `__mutmut_` 10, 12, 15, 32, 34, 38, 40, 43, 44, 46, 48, 51, 53, 55, 58, 71, 73, 77, 79, 82, 99, 101, 104, 105, 107, 109, 112, 114, 116, 119, 120, 122, 124, 127, 155, 157, 160, 161, 163, 165, 168, 183, 185, 189, 191, 194, 196, 198, 201, 202 (all `_parse_unified_response`)
- **C2 (35)**: `_parse_unified_response__mutmut_` 31, 35, 36, 45, 47, 49, 50, 70, 74, 75, 76, 80, 81, 106, 108, 110, 111, 121, 123, 125, 126, 151, 152, 153, 162, 164, 166, 167, 182, 186, 187, 195, 197, 199, 200
- **C3 (9)**: `_parse_unified_response__mutmut_` 23, 25, 66, 91, 93, 137, 139, 176, 178
- **C4 (13)**: `ClothingClassificationResult.to_context_string__` 3, 5, 7; `PoseAnalysisResult.to_context_string__` 6, 13, 20, 27; `UnifiedClothingResult.to_context_string__` 23, 25; `UnifiedPoseResult.to_context_string__` 3, 5; `UnifiedThreatResult.to_context_string__` 2; `VehicleClassificationResult.to_context_string__` 5
- **C5 (11)**: `UnifiedClothingResult.to_context_string__` 8, 10, 13, 14, 16, 18, 21; `UnifiedThreatResult.to_context_string__` 7, 9, 12, 13
- **C6 (9)**: `UnifiedEnrichmentResult.to_dict__` 9, 10, 14, 16, 17, 20, 21, 22, 23
- **C7 (8)**: `ActionClassificationResult.to_context_string__6`; `ClothingClassificationResult.to_context_string__12`; `PoseAnalysisResult.to_context_string__33`; `UnifiedClothingResult.to_context_string__27`; `UnifiedEnrichmentResult.to_context_string__13`; `UnifiedPoseResult.to_context_string__7`; `UnifiedThreatResult.to_context_string__15`; `UnifiedVehicleResult.to_context_string__7`
- **C8 (6)**: `get_model_status__` 2, 3, 4, 5; `preload_model__` 4, 7
- **C9 (4)**: `get_model_status__` 6, 10, 11, 12
- **C10 (4)**: `get_model_status__13`; `preload_model__` 12, 14, 16
- **C11 (4)**: `is_circuit_open__` 4, 6; `reset_circuit_breaker__` 4, 6
- **C12 (2)**: `_is_retryable_error__` 4, 5 · **C13 (1)**: `ActionClassificationResult.has_security_alerts__2` · **C14 (1)**: `get_model_status__16` · **C15 (1)**: `UnifiedClothingResult.to_context_string__4`

## Why the existing tests miss the parse clusters (root cause)

`test_parse_full_response` (test*enrichment_client.py:2955) supplies **every** key in every sub-dict → the `.get(key, default)` default branch never fires with a missing key (kills C1/C2 only for the mutated field it happens to assert; it asserts `pose_class`, `gender`, `make`, `has_threat`, `inference_time_ms` — the other ~17 default sites are unchecked even in the full test, which is why e.g. `_58` (`is_suspicious` default `False`→`True`) survived \_in the partial path* and name-key clobbers on unasserted fields survived the full test too). `test_parse_partial_response` (:3027) sends a pose sub-dict with **all** keys present → default branch still unexercised. C2 additionally needs full-sub-dict asserts on fields the full test doesn't check (a clobbered key returns the default, and a partial dict would mask that). C3 (`keypoints=None` etc.) fires even with complete payloads — only fields nobody asserts.

## Drafted tests (UNVERIFIED — not yet run red/green)

**TDD procedure (all tests below, one line):** with the mutant's trampoline active the new assert **fails red** against the mutated line; reverting to the original the test **passes green**. Kill-mechanics per cluster: C1/C3 → partial-sub-dict defaults asserted; C2 → full-sub-dict field values asserted; C4/C14/C13/C12 → exact-value asserts replace substring asserts; C6 → membership on the exact key names; C8 → header kwargs asserted on the mocked call; C11 → unknown-endpoint name must not raise.

All appended to `backend/tests/unit/services/test_enrichment_client.py` (imports `httpx`, `MagicMock`, `AsyncMock`, `pytest`, `CircuitState` imported locally per file convention — all already present at :16–45).

### 1. Parse robustness — kills C1 (50) + C2 (35) + C3 (9)

```python
class TestEnrichmentClientParseDefaults:
    """WP4.4: _parse_unified_response default-branch and key-name coverage.

    Existing parse tests always supply complete sub-dicts, so the ``.get(key,
    default)`` fallback branches and the exact lookup key names are never
    exercised. These tests feed partial sub-dicts (defaults must fill in) and
    a full sub-dict (every field must be read through its real key).
    // UNVERIFIED - not yet run red/green
    """

    def test_parse_partial_subdicts_get_default_values(self, client: EnrichmentClient) -> None:
        """Empty sub-dicts must fall back to documented defaults for every field."""
        data = {
            "models_loaded": [],
            "pose": {},
            "clothing": {},
            "demographics": {},
            "vehicle": {},
            "threat": {},
        }

        result = client._parse_unified_response(data)

        assert result.inference_time_ms == 0.0
        assert result.pose is not None
        assert result.pose.keypoints == []
        assert result.pose.pose_class == "unknown"
        assert result.pose.confidence == 0.0
        assert result.pose.is_suspicious is False
        assert result.clothing is not None
        assert result.clothing.categories == []
        assert result.clothing.is_suspicious is False
        assert result.demographics is not None
        assert result.demographics.age_range == "unknown"
        assert result.demographics.age_confidence == 0.0
        assert result.demographics.gender == "unknown"
        assert result.demographics.gender_confidence == 0.0
        assert result.vehicle is not None
        assert result.vehicle.make is None
        assert result.vehicle.model is None
        assert result.vehicle.color is None
        assert result.vehicle.type == "unknown"
        assert result.vehicle.confidence == 0.0
        assert result.threat is not None
        assert result.threat.threats == []
        assert result.threat.has_threat is False
        assert result.threat.max_severity == "none"

    def test_parse_full_subdicts_read_every_field(self, client: EnrichmentClient) -> None:
        """Every sub-field must be looked up by its real key name.

        Complements ``test_parse_full_response`` which asserts only a subset of
        fields, letting clobbered ``.get()`` key names (which silently fall back
        to defaults) survive.
        """
        data = {
            "inference_time_ms": 250.5,
            "pose": {
                "keypoints": [{"x": 0.5, "y": 0.3, "confidence": 0.95, "name": "nose"}],
                "pose_class": "standing",
                "confidence": 0.92,
                "is_suspicious": False,
            },
            "clothing": {
                "categories": [{"category": "casual", "confidence": 0.85}],
                "is_suspicious": True,
            },
            "demographics": {
                "age_range": "25-35",
                "age_confidence": 0.78,
                "gender": "male",
                "gender_confidence": 0.92,
            },
            "vehicle": {
                "make": "Toyota",
                "model": "Camry",
                "color": "silver",
                "type": "sedan",
                "confidence": 0.88,
            },
            "threat": {
                "threats": [{"type": "knife", "confidence": 0.85}],
                "has_threat": True,
                "max_severity": "high",
            },
        }

        result = client._parse_unified_response(data)

        assert result.inference_time_ms == 250.5
        assert result.pose is not None
        assert result.pose.keypoints == data["pose"]["keypoints"]
        assert result.pose.pose_class == "standing"
        assert result.pose.confidence == 0.92
        assert result.pose.is_suspicious is False
        assert result.clothing is not None
        assert result.clothing.categories == data["clothing"]["categories"]
        assert result.clothing.is_suspicious is True
        assert result.demographics is not None
        assert result.demographics.age_range == "25-35"
        assert result.demographics.age_confidence == 0.78
        assert result.demographics.gender == "male"
        assert result.demographics.gender_confidence == 0.92
        assert result.vehicle is not None
        assert result.vehicle.make == "Toyota"
        assert result.vehicle.color == "silver"
        assert result.vehicle.type == "sedan"
        assert result.vehicle.confidence == 0.88
        assert result.threat is not None
        assert result.threat.threats == data["threat"]["threats"]
        assert result.threat.has_threat is True
        assert result.threat.max_severity == "high"
```

### 2. `UnifiedEnrichmentResult.to_dict` key names + nested payloads — kills C6 (9)

```python
    def test_to_dict_exact_field_names_and_payloads(self) -> None:
        """WP4.4: assert the exact serialization keys and nested dict payloads.

        The existing ``test_to_dict`` checks membership only for pose/clothing/
        demographics/threat/reid_embedding; clobbered key names ("VEHICLE",
        "XXpetXX") and the ``field_value.to_dict()`` -> ``None`` swap slip
        through. // UNVERIFIED - not yet run red/green
        """
        from backend.services.enrichment_client import (
            UnifiedClothingResult,
            UnifiedEnrichmentResult,
            UnifiedThreatResult,
            UnifiedVehicleResult,
        )

        result = UnifiedEnrichmentResult(
            clothing=UnifiedClothingResult(
                categories=[{"category": "casual", "confidence": 0.85}],
                is_suspicious=False,
            ),
            vehicle=UnifiedVehicleResult(
                make="Toyota",
                model="Camry",
                color="silver",
                type="sedan",
                confidence=0.88,
            ),
            threat=UnifiedThreatResult(threats=[], has_threat=False, max_severity="none"),
            pet={"type": "dog", "breed": "labrador", "confidence": 0.95},
            action={"top_action": "walking", "confidence": 0.88},
            depth={"relative_depth": 0.4, "estimated_distance_m": 5.0},
            models_loaded=["pose"],
            inference_time_ms=10.0,
        )

        serialized = result.to_dict()

        assert serialized["vehicle"] == {
            "make": "Toyota",
            "model": "Camry",
            "color": "silver",
            "type": "sedan",
            "confidence": 0.88,
        }
        assert serialized["pet"] == {"type": "dog", "breed": "labrador", "confidence": 0.95}
        assert serialized["action"] == {"top_action": "walking", "confidence": 0.88}
        assert serialized["depth"] == {"relative_depth": 0.4, "estimated_distance_m": 5.0}
        assert serialized["clothing"] == {
            "categories": [{"category": "casual", "confidence": 0.85}],
            "is_suspicious": False,
        }
        assert serialized["threat"] == {"threats": [], "has_threat": False, "max_severity": "none"}
        assert serialized["inference_time_ms"] == 10.0
```

### 3. NEM-3147 trace headers + URL on status/preload calls — kills C8 (6)

```python
    @pytest.mark.asyncio
    async def test_status_and_preload_requests_carry_trace_headers(
        self, client: EnrichmentClient
    ) -> None:
        """WP4.4: get_model_status/preload_model must send the URL and trace headers.

        NEM-3147 requires W3C Trace Context headers on *all* enrichment calls;
        tests mock the transport wholesale and never inspect headers, so
        ``headers=None`` / URL-clobber mutants survive. // UNVERIFIED - not yet run red/green
        """
        expected = {"traceparent": "00-test-trace", "x-request-id": "rid-1"}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"loaded_models": []}

        with (
            patch(
                "backend.services.enrichment_client.get_correlation_headers",
                return_value=expected,
            ),
        ):
            client._http_client.get = AsyncMock(return_value=mock_response)
            await client.get_model_status()

            get_url = client._http_client.get.call_args.args[0]
            assert get_url == "http://test-enrichment:8094/models/status"
            assert client._http_client.get.call_args.kwargs["headers"] == expected

            client._http_client.post = AsyncMock(return_value=mock_response)
            await client.preload_model("pose")

            post_url = client._http_client.post.call_args.args[0]
            assert post_url == "http://test-enrichment:8094/models/preload"
            assert client._http_client.post.call_args.kwargs["headers"] == expected
```

(Append inside `class TestEnrichmentClientPreloadModel` or as its own class — uses the `client` fixture whose `mock_settings.enrichment_url` is `http://test-enrichment:8094`.)

### 4. Circuit-breaker unknown-endpoint fallback — kills C11 (4)

```python
    def test_breaker_lookup_falls_back_to_enrich_for_unknown_endpoint(
        self, client: EnrichmentClient
    ) -> None:
        """WP4.4: unknown endpoint names must fall back to the enrich breaker.

        Dropping the ``self._breakers["enrich"]`` default makes
        ``breakers.get(endpoint)`` return None -> AttributeError.
        // UNVERIFIED - not yet run red/green
        """
        from backend.services.circuit_breaker import CircuitState

        assert client.is_circuit_open("totally-unknown-endpoint") is False

        # Driving the shared enrich breaker to OPEN must be *visible* through an
        # unknown name: that is precisely the enrich-fallback contract.
        client._breakers["enrich"]._state = CircuitState.OPEN
        assert client.is_circuit_open("totally-unknown-endpoint") is True

        client._breakers["enrich"]._state = CircuitState.CLOSED
        client.reset_circuit_breaker("totally-unknown-endpoint")
        assert client._breakers["enrich"]._failure_count == 0
```

### 5. Retry/alert numeric boundaries — kills C12 (2) + C13 (1)

```python
    def test_is_retryable_error_http_500_boundary(self, client: EnrichmentClient) -> None:
        """WP4.4: HTTP 500 is the retry boundary and must stay retryable.

        ``>= 500`` -> ``> 500``/``>= 501`` survives because tests probe only 503
        and 400. // UNVERIFIED - not yet run red/green
        """
        for code in (500, 502, 503, 599):
            mock_response = MagicMock()
            mock_response.status_code = code
            error = httpx.HTTPStatusError(
                "Server error", request=MagicMock(), response=mock_response
            )
            assert client._is_retryable_error(error) is True, f"HTTP {code} must retry"

    def test_has_security_alerts_risk_weight_070_boundary(self) -> None:
        """WP4.4: risk_weight exactly 0.7 must alert (``>=`` not ``>``).

        Tests use 0.75/True and 0.5/False but never the boundary itself.
        // UNVERIFIED - not yet run red/green
        """
        at_threshold = ActionClassificationResult(
            action="running",
            confidence=0.90,
            is_suspicious=False,
            risk_weight=0.7,
            all_scores={},
            inference_time_ms=100.0,
        )
        assert at_threshold.has_security_alerts() is True

        below = ActionClassificationResult(
            action="walking",
            confidence=0.90,
            is_suspicious=False,
            risk_weight=0.69,
            all_scores={},
            inference_time_ms=100.0,
        )
        assert below.has_security_alerts() is False
```

### 6. Error-dict content — kills C14 (1)

```python
    @pytest.mark.asyncio
    async def test_get_model_status_error_carries_exception_message(
        self, client: EnrichmentClient
    ) -> None:
        """WP4.4: the ``error`` field must carry the real message, not "None".

        ``str(e)`` -> ``str(None)`` survives because tests assert only key
        presence. // UNVERIFIED - not yet run red/green
        """
        client._http_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        result = await client.get_model_status()

        assert result["error"] == "Connection refused"
        assert result["loaded_models"] == []
```

### 7. Exact ALERT labels — kills C4 (13)

```python
class TestContextStringExactAlertLabels:
    """WP4.4: substring-only ALERT asserts cannot see XX-padding or CAPS clobbers.

    These assert the full line content. // UNVERIFIED - not yet run red/green
    """

    def test_pose_analysis_context_exact_alert_lines(self) -> None:
        result = PoseAnalysisResult(
            keypoints=[],
            posture="crouching",
            alerts=["crouching", "lying_down", "hands_raised", "fighting_stance"],
            inference_time_ms=10.0,
        )
        context = result.to_context_string()
        assert "  [ALERT: Person crouching - potential hiding/break-in]\n" in context
        assert "  [ALERT: Person lying down - possible medical emergency]\n" in context
        assert "  [ALERT: Hands raised - possible surrender/robbery]\n" in context
        assert "  [ALERT: Fighting stance detected - potential aggression]\n" in context

    def test_clothing_classification_context_exact_labels(self) -> None:
        suspicious = ClothingClassificationResult(
            clothing_type="balaclava",
            color="black",
            style="concealing",
            confidence=0.90,
            top_category="face_covering",
            description="Black balaclava face covering",
            is_suspicious=True,
            is_service_uniform=False,
            inference_time_ms=48.0,
        )
        assert "  [ALERT: Potentially suspicious attire detected]\n" in (
            suspicious.to_context_string()
        )

        uniform = ClothingClassificationResult(
            clothing_type="uniform",
            color="brown",
            style="work",
            confidence=0.88,
            top_category="uniform",
            description="Brown delivery uniform",
            is_suspicious=False,
            is_service_uniform=True,
            inference_time_ms=45.0,
        )
        assert "  [Service/delivery worker uniform detected]\n" in uniform.to_context_string()

    def test_unified_pose_and_clothing_context_exact_labels(self) -> None:
        pose = UnifiedPoseResult(keypoints=[], pose_class="crouching", confidence=0.85, is_suspicious=True)
        assert "  [ALERT: Suspicious posture detected]\n" in pose.to_context_string()

        clothing = UnifiedClothingResult(
            categories=[{"category": "hoodie_dark", "confidence": 0.90}], is_suspicious=True
        )
        assert "  [ALERT: Potentially suspicious attire]\n" in clothing.to_context_string()

    def test_vehicle_commercial_suffix_exact(self) -> None:
        result = VehicleClassificationResult(
            vehicle_type="delivery_van",
            display_name="Delivery Van",
            confidence=0.88,
            is_commercial=True,
            all_scores={"delivery_van": 0.88},
            inference_time_ms=42.0,
        )
        assert result.to_context_string().endswith("[Commercial/delivery vehicle]")

    def test_unified_threat_no_threat_line_exact(self) -> None:
        from backend.services.enrichment_client import UnifiedThreatResult

        result = UnifiedThreatResult(threats=[], has_threat=False, max_severity="none")
        assert result.to_context_string() == "Threat detection: No threats detected"
```

### 8. (Optional cheap extra) multi-line format — kills C7 (8, LOW-VALUE)

```python
    def test_multi_section_context_strings_are_newline_separated(self) -> None:
        """WP4.4 (low-value): the join separator is "\n", not any string containing \n."""
        action = ActionClassificationResult(
            action="loitering", confidence=0.8, is_suspicious=True,
            risk_weight=0.8, all_scores={}, inference_time_ms=10.0,
        )
        assert "\n  [ALERT" in action.to_context_string()
        assert "\n  Confidence: " in action.to_context_string()
        # // UNVERIFIED - not yet run red/green
```

## Kill-mechanics notes (TDD detail per cluster)

- **C1/C3**: partial-sub-dict test (Test 1a) red on every default-flip and expr-to-None mutant (asserted default ≠ mutated value), green on original.
- **C2**: full-sub-dict test (Test 1b) red on every key clobber (mutated lookup returns the _default_, asserted value is the _supplied_ one), green on original. A partial-only test would NOT kill C2 (default == default on both sides) — both tests are required.
- **C4/C14/C13/C12/C11/C6/C8**: value/equality asserts red-on-mutant per drafted code; all green against original (constructed from the source's actual literals/behavior).
- **C9/C15**: no test recommended — semantically identical (`typing.cast` runtime no-op; dead-guard short-circuit). Candidate for mutmut ignore/exclude list (`cast(` type-string, `or True` on guarded ternary).
- **C5/C7/C10**: LOW-VALUE — recommend accepting as surviving or (C7) adopting Test 8. C10 (log args) should stay unasserted; C5 defaults are dead under real payloads.
